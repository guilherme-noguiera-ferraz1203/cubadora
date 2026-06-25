"""App central — orquestra máquina, banco, integração, calibração, login e comandos.

Fluxo fiel ao ControllerEstatica/ControllerCommon do Java:
  comando? -> login? -> etiqueta válida? -> processa etiqueta (CEP/nota+volumes) ->
  mede -> (aferição se não calibrado | cubagem real: conta, totaliza, integra).
"""

from __future__ import annotations

import logging
import threading

from ..comandos import build_default_dispatcher
from ..config.models import AppConfig
from ..cubagem import Cubagem
from ..cubagem.calibracao import Calibracao
from ..cubagem.etiqueta import parse_etiqueta
from ..cubagem.calibracao_sensores import CalibracaoAssistente, calibrar_por_cubo
from ..cubagem.nota_volume import ListNotaVolume, Totalizacao
from ..cubagem.dimensions import altura_com_ajuste, comprimento_com_ajuste, largura_com_ajuste
from ..drivers.ultrasonic import IndexSensor
from ..drivers.barcode import create_leitor
from ..drivers.lcd import LcdView, create_lcd
from ..drivers.ultrasonic import SensorOutOfRangeError
from ..integracao import CloudClient, IntegracaoManager
from ..maquina import Hardware, create_maquina
from ..maquina.sorter import Sorter
from ..maquina.workers import HeartbeatWorker, RebootWorker, TemperaturaWorker
from ..persistence import Database
from .. import __version__ as SW_VERSION
from . import sistema
from .atualizacao import Atualizacao
from .contador import ContadorService
from .fleet_agent import FleetAgent
from .login import Login

log = logging.getLogger(__name__)


class App:
    def __init__(self, config: AppConfig, simulado: bool = True, db_path: str = "cubagem.db",
                 config_path: str | None = None):
        self.config = config
        self.config_path = config_path
        self.simulado = simulado
        self.db = Database(db_path)
        self.hw = Hardware(config, simulado)
        self.maquina = create_maquina(self.hw, config)
        self.integracao = IntegracaoManager(config, self.db)
        self.cloud = CloudClient(config.cloud, config.serial_maquina, habilitada=False)
        self.calibracao = Calibracao(config.calibracao, config.modo_teste)
        self.assistente = CalibracaoAssistente()
        self.login = Login(config.login)
        self.contador = ContadorService(self.db)
        self.lista_notas = ListNotaVolume()
        self.totalizacao = Totalizacao()
        self.dispatcher = build_default_dispatcher(self)

        # periféricos (Onda 2): LCD + leitor de código de barras + workers
        self.lcd = create_lcd(config.lcd, simulado)
        self.lcd_view = LcdView(self.lcd)
        self.leitor = create_leitor(config.leitor, self._on_barcode, self.hw.atmega, simulado)
        self.sorter = Sorter(self.hw.modbus, config.sorter)
        self.atualizacao = Atualizacao(config.frota.servidor, SW_VERSION)
        self.fleet = FleetAgent(self)
        self._workers: list = []

        # flags de modo (alteráveis por comando)
        self.modo_envelope = False
        self.modo_debug = config.modo_teste
        self.bordas = False

        self._executando = False
        self.ultima_cubagem: Cubagem | None = None
        self.ultima_etiqueta = ""
        self.ultima_integracao = "—"
        self._ultimo_id = 0
        self.maquina.add_cubagem_listener(self._on_cubagem)

    # ----------------------------------------------------------------- medição
    def _on_cubagem(self, cub: Cubagem) -> None:
        self.ultima_cubagem = cub
        self._ultimo_id = self.db.salvar_cubagem(cub.etiqueta, cub.altura, cub.largura,
                                                 cub.comprimento, cub.peso, cub.volume_m3)
        try:
            self.lcd_view.on_cubagem(cub)
        except Exception:  # noqa: BLE001
            pass

    def _on_barcode(self, codigo: str) -> None:
        """Chamado pelo leitor de código de barras a cada leitura."""
        log.info("Código lido: %s", codigo)
        try:
            self.tratar_etiqueta(codigo)
        except Exception:  # noqa: BLE001
            log.exception("Erro ao tratar código lido")

    def tratar_etiqueta(self, texto: str) -> dict:
        """Porta de ControllerEstatica.tratarEtiqueta + ControllerCommon."""
        texto = (texto or "").strip()

        # 0) cubo de aferição (código de barras específico) -> calibra
        cod_cubo = self.config.calibracao.codigo_cubo
        if texto and cod_cubo and texto == cod_cubo:
            return {"tipo": "calibracao", "mensagem": self.calibrar_com_cubo()}

        # 1) comando operacional (inclui *cal* -> calibração pelo cubo)
        msg = self.dispatcher.execute(texto)
        if msg is not None:
            return {"tipo": "comando", "mensagem": msg}

        # 2) login (quando habilitado e já aferido)
        if self.login.is_enabled() and not self.login.is_logged() and self.calibracao.is_calibrado():
            if texto and self.login.login(texto):
                return {"tipo": "login", "mensagem": f"Bem-vindo, {texto}"}
            return {"tipo": "erro", "mensagem": "Informe o usuário para login"}

        # 3) etiqueta vazia inválida (quando já aferido)
        et = self.config.etiqueta
        if (self.calibracao.is_calibrado() and not texto
                and not et.nota_mais_volumes and not et.danfe):
            return {"tipo": "erro", "mensagem": "Etiqueta inválida"}

        # 4) processa etiqueta (CEP / nota+volumes)
        etiqueta_proc = self.lista_notas.process_etiqueta(texto, et.nota_mais_volumes)
        if etiqueta_proc == "" and et.nota_mais_volumes and "+" in texto:
            return {"tipo": "info", "mensagem": "Nota registrada. Escaneie os volumes."}

        # 5) medição
        cub = self.medir(etiqueta_proc)

        # 6) aferição (se ainda não calibrado)
        if not self.calibracao.is_calibrado():
            ok = self.calibracao.calibrar(cub)
            return {"tipo": "afericao", "ok": ok,
                    "mensagem": "Aferição OK" if ok else "Execute a aferição novamente",
                    "cubagem": cub.to_dict()}

        # 7) cubagem real
        if cub.is_empty():
            self.contador.inc_erro_cubagem()
            return {"tipo": "erro", "mensagem": "Valor zerado em um dos parâmetros",
                    "cubagem": cub.to_dict()}

        self.contador.inc_cubagem()
        self.login.update_uso()
        if self.config.totalizacao_peso:
            self.totalizacao.add(cub.volume_m3, cub.peso)
        status_integ = "—"
        if etiqueta_proc:
            status_integ = self.integracao.executar(etiqueta_proc, cub, "auto")
            self.db.atualizar_integracao(self._ultimo_id, status_integ)
            if status_integ == "enviado":
                self.db.inc_contador("integracao_ok", 1)
            elif status_integ in ("fila", "erro"):
                self.db.inc_contador("integracao_erro", 1)
            self.cloud.enviar_cubagem(etiqueta_proc, cub)
        self.ultima_integracao = status_integ
        return {"tipo": "cubagem", "cubagem": cub.to_dict(), "integracao": status_integ}

    def medir(self, etiqueta: str = "") -> Cubagem:
        if self._executando:
            raise RuntimeError("Já existe uma medição em andamento")
        self._executando = True
        self.ultima_etiqueta = etiqueta
        self.contador.update_millis_start_operacao()
        try:
            if self.modo_envelope:
                cub = self._medir_envelope(etiqueta)
            else:
                cub = self.maquina.ler_cubagem(etiqueta)
            return cub
        except SensorOutOfRangeError:
            self.db.inc_contador("erro_fora_faixa", 1)
            raise
        finally:
            self._executando = False
            self.contador.inc_segundos_operacao()

    def _medir_envelope(self, etiqueta: str) -> Cubagem:
        """Modo envelope: dimensões = 1, só pesa."""
        cub = Cubagem(altura=1.0, largura=1.0, comprimento=1.0, etiqueta=etiqueta)
        try:
            cub.peso = self.hw.balanca.get_media_peso()
        except Exception:  # noqa: BLE001
            cub.peso = 0.0
        self._on_cubagem(cub)
        return cub

    # ----------------------------------------------------------------- comandos
    def tarar(self) -> str:
        """Zera a balança. Em balança Modbus, escreve no registro de tara configurado."""
        b = self.config.balanca
        reg_tara = getattr(b, "registro_tara", 0)
        if reg_tara and not self.simulado:
            try:
                self.hw.modbus.write("Tara", b.endereco, reg_tara, 1)
                return "Tara enviada à balança"
            except Exception as exc:  # noqa: BLE001
                return f"Erro ao tarar: {exc}"
        log.info("Comando tara solicitado")
        return "Tara solicitada (configure o registro de tara da balança)"

    # --------------------------------------------------- configuração (web)
    def get_config_dict(self) -> dict:
        from ..config import config_to_dict
        return config_to_dict(self.config)

    def atualizar_config(self, secao: str, dados: dict) -> str:
        """Atualiza uma seção da config (ex.: 'balanca') e persiste no YAML."""
        from ..config import coerce
        from dataclasses import is_dataclass

        obj = getattr(self.config, secao, None)
        if obj is None or not is_dataclass(obj):
            # escalares de topo
            if secao in ("modelo_maquina", "casa_decimal_medidas", "serial_maquina",
                         "modo_teste", "totalizacao_peso"):
                setattr(self.config, secao, dados)
            else:
                return f"Seção desconhecida: {secao}"
        else:
            for k, v in dados.items():
                if hasattr(obj, k):
                    setattr(obj, k, coerce(getattr(obj, k), v))
        # aplica mudanças "ao vivo" quando possível
        self._reaplicar_config(secao)
        return self._salvar_config(secao)

    def _reaplicar_config(self, secao: str) -> None:
        # a balança Modbus lê a config a cada leitura; a I²C copia casas decimais no init
        if secao == "balanca" and hasattr(self.hw.balanca, "casa_decimal_peso"):
            self.hw.balanca.casa_decimal_peso = self.config.balanca.casa_decimal_peso
        if secao == "calibracao":
            self.calibracao.config = self.config.calibracao

    def _salvar_config(self, secao: str) -> str:
        if not self.config_path:
            return f"Seção '{secao}' atualizada (em memória; sem arquivo para salvar)"
        try:
            from ..config import save_config
            save_config(self.config, self.config_path)
            return f"Seção '{secao}' atualizada e salva"
        except Exception as exc:  # noqa: BLE001
            return f"Seção '{secao}' atualizada (falha ao salvar: {exc})"

    def escrever_parametro_balanca(self, registro: int, valor: int) -> str:
        """Escreve um registro/parâmetro diretamente na balança (Modbus)."""
        if self.simulado:
            return f"(simulado) escreveria {valor} no registro {registro}"
        try:
            self.hw.modbus.write("Parâmetro balança", self.config.balanca.endereco, registro, valor)
            return f"Parâmetro gravado: registro {registro} = {valor}"
        except Exception as exc:  # noqa: BLE001
            return f"Erro ao gravar parâmetro: {exc}"

    def ler_peso_atual(self) -> float:
        try:
            return self.hw.balanca.get_media_peso()
        except Exception:  # noqa: BLE001
            return 0.0

    # --------------------------------------------------- diagnóstico / comissionamento
    def diagnostico(self) -> dict:
        """Testa o barramento, cada sensor e a balança — para deixar o equipamento apto."""
        sensores = []
        cfg = self.config.sensor
        enderecos = [a for a in (list(cfg.enderecos) + list(cfg.enderecos2)) if a]
        for addr in enderecos:
            try:
                raw = self.hw.sensor.read_raw(addr)
                versao = self.hw.sensor.read_version(addr)
            except Exception:  # noqa: BLE001
                raw, versao = -1, -1
            sensores.append({
                "endereco": addr,
                "respondendo": raw >= 0,
                "distancia_cm": round(raw / 10.0, 1) if raw > 0 else 0.0,
                "versao": versao if versao and versao > 0 else None,
            })
        peso = self.ler_peso_atual()
        balanca_ok = peso >= 0
        sensores_ok = all(s["respondendo"] for s in sensores) and bool(sensores)
        apto = sensores_ok and balanca_ok and (self.calibracao.is_calibrado() or self.config.modo_teste)
        return {
            "sensores": sensores,
            "sensores_ok": sensores_ok,
            "balanca": {"peso": round(peso, 3), "ok": balanca_ok},
            "aferido": self.calibracao.is_calibrado(),
            "erros": {"checksum": self.hw.sensor.s.error_count, "timeout": self.hw.sensor.s.timeout_count},
            "apto_producao": apto,
        }

    def ler_sensores_ao_vivo(self) -> dict:
        """Leitura ao vivo (porta do DebugSensorDistancia): distâncias + dimensões + peso."""
        mapa = self.hw.sensor.ler_sensores()
        aj = self.config.ajustes
        d_alt = mapa.get(IndexSensor.ALTURA, 0.0)
        d_fun = mapa.get(IndexSensor.FUNDO, 0.0)
        d_esq = mapa.get(IndexSensor.ESQUERDA, 0.0)
        d_dir = mapa.get(IndexSensor.DIREITA, 0.0)
        return {
            "distancias": {"altura": round(d_alt, 2), "fundo": round(d_fun, 2),
                           "esquerda": round(d_esq, 2), "direita": round(d_dir, 2)},
            "dimensoes": {
                "altura": round(altura_com_ajuste(d_alt, aj), 1),
                "largura": round(largura_com_ajuste(d_fun, aj), 1),
                "comprimento": round(comprimento_com_ajuste(d_esq, d_dir, aj), 1),
            },
            "peso": round(self.ler_peso_atual(), 3),
        }

    # --------------------------------------------------- calibração dos sensores
    def calibrar_capturar(self, altura: float, largura: float, comprimento: float) -> dict:
        """Captura um ponto: lê as distâncias atuais e associa às dimensões reais informadas."""
        mapa = self.hw.sensor.ler_sensores()
        distancias = {
            "altura": mapa.get(IndexSensor.ALTURA, 0.0),
            "fundo": mapa.get(IndexSensor.FUNDO, 0.0),
            "comprimento": mapa.get(IndexSensor.ESQUERDA, 0.0) + mapa.get(IndexSensor.DIREITA, 0.0),
        }
        n = self.assistente.capturar(distancias, {"altura": altura, "largura": largura, "comprimento": comprimento})
        return {"pontos": n, "pode_calcular": self.assistente.pode_calcular(), "distancias": distancias}

    def calibrar_calcular(self) -> dict:
        return self.assistente.calcular()

    def calibrar_aplicar(self, ajustes: dict) -> str:
        msg = self.atualizar_config("ajustes", ajustes)
        self.assistente.limpar()
        return f"Calibração aplicada. {msg}"

    def calibrar_limpar(self) -> str:
        self.assistente.limpar()
        return "Pontos de calibração descartados"

    def calibrar_com_cubo(self) -> str:
        """Calibração pelo CUBO DE AFERIÇÃO (comando *cal*).

        Mede o cubo na estação e ajusta os offsets (e o peso) para casar com as dimensões
        conhecidas do cubo. Marca a máquina como aferida.
        """
        mapa = self.hw.sensor.ler_sensores()
        distancias = {
            "altura": mapa.get(IndexSensor.ALTURA, 0.0),
            "fundo": mapa.get(IndexSensor.FUNDO, 0.0),
            "comprimento": mapa.get(IndexSensor.ESQUERDA, 0.0) + mapa.get(IndexSensor.DIREITA, 0.0),
        }
        peso = self.ler_peso_atual()
        c = self.config.calibracao
        cubo = {"altura": c.altura, "largura": c.largura, "comprimento": c.comprimento, "peso": c.peso}
        novos, ajuste_peso, ok = calibrar_por_cubo(distancias, peso, cubo, self.config.ajustes)
        if not ok:
            self.set_status_erro("Cubo de aferição não detectado. Verifique a posição.")
            return "Cubo de aferição não detectado (sensores/balança sem leitura)"
        from ..maquina.base import Cor
        self.atualizar_config("ajustes", novos)
        self.atualizar_config("balanca", {"ajuste_peso": ajuste_peso})
        self.calibracao.set_calibrado(True)
        self.maquina.set_status(Cor.VERDE, "Aferição OK")
        log.info("Calibração pelo cubo: ajustes=%s ajuste_peso=%.3f", novos, ajuste_peso)
        return (f"Aferição OK pelo cubo ({c.altura}x{c.largura}x{c.comprimento} cm, {c.peso} kg). "
                f"Offsets recalibrados e peso ajustado em {ajuste_peso:+.3f} kg.")

    def set_status_erro(self, texto: str) -> None:
        from ..maquina.base import Cor
        self.maquina.set_status(Cor.VERMELHO, texto)

    def set_limites_sensor(self, index: int, minimo: float, maximo: float) -> str:
        if 0 <= index < 4:
            self.config.sensor.minimo_sensor[index] = float(minimo)
            self.config.sensor.maximo_sensor[index] = float(maximo)
            return self._salvar_config("sensor")
        return "Índice de sensor inválido (0-3)"

    # --------------------------------------------------- sistema (rede / Pi)
    def get_sistema_info(self) -> dict:
        return sistema.get_pi_info()

    def configurar_sistema(self, dados: dict) -> str:
        msgs = []
        if dados.get("hostname"):
            msgs.append(sistema.set_hostname(dados["hostname"]))
        if dados.get("wifi_ssid"):
            msgs.append(sistema.configurar_wifi(dados["wifi_ssid"], dados.get("wifi_senha", "")))
        if dados.get("ip_modo"):
            msgs.append(sistema.configurar_ip(dados["ip_modo"], dados.get("ip", ""),
                                              dados.get("gateway", ""), dados.get("dns", "")))
        return " | ".join(msgs) if msgs else "Nada para configurar"

    def acao_sistema(self, acao: str) -> str:
        if acao == "reboot":
            from ..comandos.dispatcher import _reiniciar
            return _reiniciar("")
        if acao == "shutdown":
            from ..comandos.dispatcher import _desligar
            return _desligar("")
        if acao == "restart_servico":
            return sistema.reiniciar_servico()
        return "Ação desconhecida"

    def alternar_integracao(self) -> str:
        self.integracao.habilitada = not self.integracao.habilitada
        return f"Integração {'ligada' if self.integracao.habilitada else 'desligada'}"

    def reexecutar_integracao(self) -> str:
        if self.ultima_cubagem and self.ultima_etiqueta:
            self.integracao.executar(self.ultima_etiqueta, self.ultima_cubagem, "manual")
            return "Integração reexecutada"
        return "Nenhuma cubagem para reexecutar"

    def limpar_fila(self) -> str:
        pend = self.db.integracoes_pendentes(limit=10_000)
        for p in pend:
            self.db.marcar_integracao(p["id"], "cancelado")
        return f"Fila de integração limpa ({len(pend)} itens)"

    def limpar_banco(self) -> str:
        self.db.limpar_cubagens()
        return "Banco de cubagens limpo"

    def logout(self) -> str:
        self.login.logout()
        return "Logout efetuado"

    def toggle_envelope(self) -> str:
        self.modo_envelope = not self.modo_envelope
        return f"Modo envelope {'ligado' if self.modo_envelope else 'desligado'}"

    def toggle_debug(self) -> str:
        self.modo_debug = not self.modo_debug
        return f"Modo debug {'ligado' if self.modo_debug else 'desligado'}"

    def toggle_bordas(self) -> str:
        self.bordas = not self.bordas
        return f"Bordas {'ligadas' if self.bordas else 'desligadas'} (reinicie a GUI)"

    def toggle_cep(self) -> str:
        self.config.etiqueta.modo_cep = not self.config.etiqueta.modo_cep
        return f"Modo CEP {'ligado' if self.config.etiqueta.modo_cep else 'desligado'}"

    def toggle_danfe(self) -> str:
        self.config.etiqueta.danfe = not self.config.etiqueta.danfe
        return f"Modo DANFE {'ligado' if self.config.etiqueta.danfe else 'desligado'}"

    def reset_totalizacao(self) -> str:
        self.totalizacao.reset()
        return "Totalização zerada"

    def especificacao(self) -> str:
        return (f"cubagem-pi {self.config.versao} | modelo={self.config.modelo_maquina.value} | "
                f"sensores={self.config.sensor.enderecos} | serial={self.config.serial_maquina}")

    def resumo_config(self) -> str:
        c = self.config
        return (f"Modelo={c.modelo_maquina.value} | RS485={c.rs485.serial_port}@{c.rs485.baudrate} "
                f"| Web:{c.web.porta} | Versão={c.versao} | Aferido={self.calibracao.is_calibrado()}")

    def executar_camera(self) -> str:
        try:
            l, c = self.hw.camera.medir("manual")
            return f"Câmera: L={l:.1f} C={c:.1f} cm"
        except Exception as exc:  # noqa: BLE001
            return f"Erro na câmera: {exc}"

    def info_rede(self) -> str:
        info = sistema.info_rede()
        return f"IP: {info['ip']} | host: {info['hostname']}"

    def enviar_sorter(self, comando: str) -> str:
        return self.sorter.enviar_raw(comando)

    def atualizar(self) -> str:
        nova = self.atualizacao.verificar()
        if not nova:
            return "Nenhuma atualização disponível"
        return self.atualizacao.aplicar()

    def download_config(self) -> str:
        ok = self.cloud.baixar_config()
        return "Config baixada da nuvem" if ok else "Nuvem indisponível"

    # ----------------------------------------------------------------- estado
    def nome_integracao(self) -> str:
        if not self.integracao.habilitada:
            return "desligada"
        ativas = self.integracao.integracoes_ativas()
        if not ativas:
            return "nenhuma"
        return ativas[0].get("name", "ativa")

    def producao_dict(self) -> dict:
        from datetime import datetime, timedelta
        uma_hora = (datetime.now() - timedelta(hours=1)).isoformat()
        return {
            "volumes": self.db.get_contador("cubagem"),
            "vol_h": self.db.contar_cubagens_desde(uma_hora),
            "integracao_ok": self.db.get_contador("integracao_ok"),
            "integracao_erro": self.db.get_contador("integracao_erro"),
            "erro_cubagem": self.db.get_contador("erro_cubagem") + self.db.get_contador("erro_fora_faixa"),
            "totalizacao_volume": round(self.totalizacao.total_volume, 4),
            "totalizacao_peso": round(self.totalizacao.total_peso, 3),
        }

    def status_dict(self) -> dict:
        st = self.maquina.status
        return {
            "modelo": self.config.modelo_maquina.value,
            "nome_equipamento": self.config.nome_equipamento,
            "tem_logo": self.tem_logo(),
            "simulado": self.simulado,
            "executando": self._executando,
            "status_cor": st.cor.value,
            "status_texto": st.texto,
            "rede": {"ip": sistema.get_ip(), "tipo": sistema.tipo_conexao()},
            "integracao_nome": self.nome_integracao(),
            "aferido": self.calibracao.is_calibrado(),
            "logado": self.login.is_logged(),
            "modo_envelope": self.modo_envelope,
            "ultima_cubagem": self.ultima_cubagem.to_dict() if self.ultima_cubagem else None,
            "ultima_integracao": self.ultima_integracao,
            "producao": self.producao_dict(),
            "contadores": self.contador.todos(),
            "totalizacao": {"volume": round(self.totalizacao.total_volume, 4),
                            "peso": round(self.totalizacao.total_peso, 3),
                            "quantidade": self.totalizacao.quantidade},
            "integracao_habilitada": self.integracao.habilitada,
            "versao": SW_VERSION,
            "unidade": self.config.frota.unidade,
            "kiosk_modo_producao": bool(getattr(getattr(self.config, "kiosk", None), "modo_producao", False)),
        }

    # ----------------------------------------------------------------- logo
    def _logo_file(self) -> str:
        return self.config.logo_path or "data/logo.png"

    def tem_logo(self) -> bool:
        import os
        return os.path.exists(self._logo_file())

    def salvar_logo(self, dados: bytes) -> str:
        import os
        caminho = self._logo_file()
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        with open(caminho, "wb") as f:
            f.write(dados)
        return "Logo salva"

    def ler_logo(self) -> bytes | None:
        if not self.tem_logo():
            return None
        with open(self._logo_file(), "rb") as f:
            return f.read()

    # ----------------------------------------------------------------- integração (API)
    def get_integracao_config(self) -> list[dict]:
        return self.config.integracao

    def salvar_integracao_config(self, lista: list[dict]) -> str:
        self.config.integracao = [i for i in lista if isinstance(i, dict)]
        return self._salvar_config("integracao")

    # ----------------------------------------------------------------- identidade / frota (adoção)
    def device_id(self) -> str:
        import hashlib
        import uuid
        if self.config.frota.device_id:
            return self.config.frota.device_id
        base = self.config.serial_maquina or hex(uuid.getnode())
        return "cub-" + hashlib.sha256(base.encode()).hexdigest()[:12]

    def identidade(self) -> dict:
        return {
            "device_id": self.device_id(),
            "nome": self.config.nome_equipamento,
            "unidade": self.config.frota.unidade,
            "modelo": self.config.modelo_maquina.value,
            "versao": SW_VERSION,
            "ip": sistema.get_ip(),
            "adotado": self.config.frota.adotado,
            "servidor": self.config.frota.servidor,
        }

    def adotar(self, servidor: str, chave: str = "") -> str:
        self.config.frota.servidor = servidor
        self.config.frota.chave = chave
        self.config.frota.adotado = True
        self.config.frota.device_id = self.device_id()
        self._salvar_config("frota")
        log.info("Equipamento adotado pelo painel de frota: %s", servidor)
        return f"Adotado por {servidor}"

    # ----------------------------------------------------------------- ciclo de vida
    def start(self) -> None:
        dev = sistema.detectar_dispositivo()
        log.info("Dispositivo: %s | SO: %s | sessão: %s", dev["modelo"], dev["os"], dev["sessao"] or "—")

        # status -> LCD
        self.maquina.add_status_listener(self.lcd_view.on_status)
        self.lcd.init()

        threading.Thread(target=self.maquina.run, name="maquina", daemon=True).start()
        self.integracao.start_retry_timer(10)

        # leitor de código de barras
        if self.leitor:
            self.leitor.start()

        # workers de fundo
        heartbeat = HeartbeatWorker(self.hw.led)
        temperatura = TemperaturaWorker(self.hw.sensor, self.config.sensor)
        reboot = RebootWorker(self.hw.atmega)
        for w in (heartbeat, temperatura, reboot):
            w.start()
            self._workers.append(w)

        self.fleet.start()   # agente de frota (heartbeat + auto-update)
        log.info("App iniciado (%s, sw=%s)", self.resumo_config(), SW_VERSION)

    def stop(self) -> None:
        self.fleet.stop()
        for w in self._workers:
            w.stop()
        if self.leitor:
            self.leitor.stop()
        self.maquina.stop()
        self.integracao.stop()
        self.contador.stop()
        self.hw.close()
        self.db.close()
