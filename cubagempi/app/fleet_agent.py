"""Agente de frota: reporta ao painel central (heartbeat), aplica a versão-alvo
e executa comandos remotos enviados pelo painel.

A cada ciclo, o equipamento envia ao servidor: identidade, unidade, versão, status, produção,
os eventos/erros novos e o resultado dos comandos executados desde o último heartbeat. O servidor
responde com a versão-alvo e a lista de comandos pendentes; o equipamento executa cada um e reporta
o resultado no próximo heartbeat.

Pull-based: só o servidor precisa de endereço fixo; os equipamentos podem estar em redes/unidades
diferentes, atrás de NAT.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import urllib.request

from .. import __version__ as SW_VERSION
from ..core.log_buffer import get_log_buffer

_DIAG_FILE = "data/ultimo_diag.json"

log = logging.getLogger(__name__)

# Comandos que derrubam/reiniciam o processo: o resultado é reportado ANTES de executar,
# senão o processo morre antes de conseguir avisar o painel.
_DESTRUTIVOS = {"reboot", "shutdown", "restart_app", "update"}


class FleetAgent:
    def __init__(self, app):
        self.app = app
        self.cfg = app.config.frota
        self._stop = threading.Event()
        self._ultimo_seq = 0
        self._executados: set = set()   # ids de comandos já executados (dedup)
        self._resultados: list = []     # resultados pendentes de reportar ao painel
        # Cache do ultimo diagnostico — PERSISTE em disco para sobreviver a restart_app/OTA.
        self._ultimo_diag: dict | None = self._carregar_diag()

    def start(self) -> None:
        if not self.cfg.servidor:
            log.info("Frota: sem servidor configurado; agente desativado.")
            return
        threading.Thread(target=self._loop, name="fleet-agent", daemon=True).start()
        log.info("Frota: agente ativo (servidor=%s)", self.cfg.servidor)

    def stop(self) -> None:
        self._stop.set()

    def _carregar_diag(self) -> dict | None:
        try:
            with open(_DIAG_FILE, encoding="utf-8") as f: return json.load(f)
        except (FileNotFoundError, ValueError):
            return None

    def _salvar_diag(self, d: dict) -> None:
        try:
            os.makedirs(os.path.dirname(_DIAG_FILE) or ".", exist_ok=True)
            with open(_DIAG_FILE, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            log.debug("Frota: falha ao persistir diag (%s)", exc)

    def _coletar_eventos(self) -> list[dict]:
        self._ultimo_seq, eventos = get_log_buffer().desde(self._ultimo_seq, ("WARNING", "ERROR", "CRITICAL"))
        return eventos[-30:]  # no máximo 30 por heartbeat

    def _estado_completo(self) -> dict:
        """Snapshot rico p/ o painel: status_dict (leve) + sistema_info (leve) + ultimo diagnostico."""
        estado: dict = {}
        try: estado["status"] = self.app.status_dict()
        except Exception as exc: estado["status_erro"] = str(exc)[:120]  # noqa: BLE001
        try: estado["sistema"] = self.app.get_sistema_info()
        except Exception as exc: estado["sistema_erro"] = str(exc)[:120]  # noqa: BLE001
        if self._ultimo_diag:
            estado["diagnostico"] = self._ultimo_diag
        return estado

    def _payload(self) -> dict:
        ident = self.app.identidade()
        return {
            "device_id": ident["device_id"],
            "nome": ident["nome"],
            "unidade": self.cfg.unidade,
            "versao": SW_VERSION,
            "modelo": ident["modelo"],
            "ip": ident["ip"],
            "status": self.app.maquina.status.texto,
            "status_cor": self.app.maquina.status.cor.value,
            "aferido": self.app.calibracao.is_calibrado(),
            "integracao": self.app.nome_integracao(),
            "producao": self.app.producao_dict(),
            "eventos": self._coletar_eventos(),
            "comandos_resultado": list(self._resultados),  # ACK dos comandos executados
            "estado": self._estado_completo(),              # snapshot rico para o painel
        }

    def heartbeat(self) -> dict | None:
        url = self.cfg.servidor.rstrip("/") + "/api/heartbeat"
        enviados = list(self._resultados)
        body = json.dumps(self._payload()).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8") or "{}")
            # entregue com sucesso -> remove os resultados que foram reportados
            for r in enviados:
                try:
                    self._resultados.remove(r)
                except ValueError:
                    pass
            return data
        except Exception as exc:  # noqa: BLE001
            log.debug("Frota: heartbeat falhou (%s)", exc)
            return None

    def _verificar_update(self, resposta: dict) -> None:
        alvo = (resposta or {}).get("versao_alvo")
        if alvo and alvo != SW_VERSION and self.cfg.auto_update:
            log.warning("Frota: versão-alvo %s difere da atual %s; atualizando...", alvo, SW_VERSION)
            self.app.atualizacao.aplicar_versao(self.cfg.servidor, alvo)  # baixa, aplica e reinicia

    def _executar_comando(self, tipo: str, par: dict) -> str:
        """Mapeia um comando do painel para uma ação no equipamento. Retorna a mensagem de resultado."""
        try:
            if tipo == "reboot":
                return self.app.acao_sistema("reboot")
            if tipo == "shutdown":
                return self.app.acao_sistema("shutdown")
            if tipo == "restart_app":
                # Reinicia a aplicação no lugar (os.execv) — funciona em kiosk e em systemd.
                self.app.atualizacao.reiniciar()
                return "Reiniciando aplicação"
            if tipo == "update":
                # Aplica imediatamente a versao indicada (parametro), caindo para a versao-alvo
                # configurada para este equipamento (config.frota lida em tempo real).
                alvo = (par.get("versao") or "").strip()
                if not alvo:
                    return "Sem versao especificada para atualizar"
                return self.app.atualizacao.aplicar_versao(self.cfg.servidor, alvo)
            if tipo == "config":
                return self.app.atualizar_config(par.get("secao", ""), par.get("dados", {}) or {})
            if tipo == "comando":
                # Acesso a TODOS os comandos do dispatcher (tara, calibrar, integração, etc.)
                return self.app.dispatcher.execute(par.get("texto", ""))
            if tipo == "diagnostico":
                # Roda o diagnostico (pesado: le sensores e balanca), PERSISTE em disco e forca
                # um heartbeat imediato para o painel receber os detalhes antes de qualquer restart.
                self._ultimo_diag = self.app.diagnostico()
                self._ultimo_diag["ts"] = datetime.datetime.now().isoformat()
                self._salvar_diag(self._ultimo_diag)
                threading.Thread(target=self.heartbeat, name="hb-diag", daemon=True).start()
                ok = self._ultimo_diag.get("apto_producao")
                return ("Diagnostico OK" if ok else "Diagnostico com problemas") + " (detalhes no painel)"
            return f"Comando desconhecido: {tipo}"
        except Exception as exc:  # noqa: BLE001
            log.exception("Frota: falha ao executar comando %s", tipo)
            return f"erro: {exc}"

    def _processar_comandos(self, resposta: dict) -> None:
        comandos = (resposta or {}).get("comandos") or []
        for cmd in comandos:
            cid = cmd.get("id")
            if cid is None or cid in self._executados:
                continue
            self._executados.add(cid)
            tipo = cmd.get("tipo", "")
            par = cmd.get("parametros") or {}
            log.warning("Frota: executando comando remoto #%s (%s)", cid, tipo)
            if tipo in _DESTRUTIVOS:
                # reporta ANTES de executar (o processo vai cair/reiniciar)
                self._resultados.append({"id": cid, "status": "executado", "resultado": f"executando {tipo}"})
                self.heartbeat()
            res = self._executar_comando(tipo, par)
            self._resultados.append({"id": cid, "status": "executado", "resultado": str(res)[:500]})

    def _intervalo(self) -> float:
        # Responsivo para controle remoto: no máximo 10s entre ciclos, respeitando valores menores.
        hb = self.cfg.heartbeat_segundos or 10
        return max(5, min(hb, 10))

    def _loop(self) -> None:
        # primeiro heartbeat logo após subir, depois no intervalo
        self._stop.wait(5)
        while not self._stop.is_set():
            resp = self.heartbeat()
            if resp is not None:
                self._verificar_update(resp)
                self._processar_comandos(resp)
            self._stop.wait(self._intervalo())
