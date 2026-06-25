"""CLP/PLC via Modbus RTU (porta de Clp485.java).

CLP no endereço 1. Mapa de registradores (D-registers) do sistema dinâmico (esteira).
"""

from __future__ import annotations

import logging

from .modbus import Modbus485

log = logging.getLogger(__name__)

ENDERECO_CLP = 1

# Registradores
REG_MAQUINA_LIBERADA = 10
REG_ETIQUETAS_RESTANTES = 100
REG_EQUIPAMENTO_CONFIGURADO = 200
REG_ENTRADA_MAQUINA = 201
REG_LEITURA_CODIGO_BARRAS = 202
REG_VELOCIDADE_ESTEIRA = 213
REG_NOVA_ETIQUETA = 240
REG_PROCESSAR_CUBAGEM = 241
REG_PARADA_CRITICA = 242
REG_CRIAR_COMPARE = 243
REG_LIBERAR_CAIXA = 244
REG_PARAR_ESTEIRA = 245
REG_CUBAGEM_FINALIZADA = 246
REG_ERRO = 300
REG_MENSAGEM_ERRO = 3000
TAMANHO_MENSAGEM_ERRO = 10
REG_SENSOR_ROLLERDRIVE_ENTRADA = 1000
REG_SENSOR_OPS290 = 1001
REG_SENSOR_CADENCIAMENTO = 1002
REG_SENSOR_INICIA_PESAGEM = 1003
REG_SENSOR_VMS = 1004
REG_SENSOR_ESTEIRA_CHEIA = 1005
REG_BOTAO_EMERGENCIA = 1007
REG_NOVA_PESAGEM = 1010


class Clp485:
    def __init__(self, modbus: Modbus485, enabled: bool = True):
        self.modbus = modbus
        self.enabled = enabled

    def write(self, name: str, registro: int, valor: int) -> None:
        if self.enabled:
            self.modbus.write(name, ENDERECO_CLP, registro, valor)

    def read(self, name: str, registro: int) -> int:
        if self.enabled:
            return self.modbus.read(name, ENDERECO_CLP, registro)
        return 0

    # estados / sensores
    def is_emergencia(self) -> bool:
        return self.read("Botao emergencia", REG_BOTAO_EMERGENCIA) != 0

    def is_peso_disponivel(self) -> bool:
        return self.read("Nova pesagem", REG_NOVA_PESAGEM) != 0

    def zerar_nova_pesagem(self) -> None:
        self.write("Nova pesagem", REG_NOVA_PESAGEM, 0)

    def existe_processar_cubagem(self) -> bool:
        return self.read("Flag processar cubagem", REG_PROCESSAR_CUBAGEM) != 0

    def zerar_processar_cubagem(self) -> None:
        self.write("Flag processar cubagem", REG_PROCESSAR_CUBAGEM, 0)

    def read_status_erro(self) -> int:
        return self.read("Status erro", REG_ERRO)

    def read_mensagem_erro(self) -> str:
        if not self.enabled:
            return ""
        return self.modbus.read_string("Mensagem erro", ENDERECO_CLP, REG_MENSAGEM_ERRO, TAMANHO_MENSAGEM_ERRO)

    # comandos
    def write_nova_etiqueta(self, valor: int) -> None:
        self.write("Nova etiqueta", REG_NOVA_ETIQUETA, valor)

    def write_etiquetas_restantes(self, valor: int) -> None:
        self.write("Etiquetas restantes", REG_ETIQUETAS_RESTANTES, valor)

    def write_parada_critica(self) -> None:
        self.write("Parada critica", REG_PARADA_CRITICA, 1)

    def write_liberar_caixa(self) -> None:
        self.write("LiberarCaixa", REG_LIBERAR_CAIXA, 1)

    def write_parar_esteira(self) -> None:
        self.write("PararEsteira", REG_PARAR_ESTEIRA, 1)

    def write_maquina_liberada(self, valor: int) -> None:
        self.write("MaquinaLiberada", REG_MAQUINA_LIBERADA, valor)

    def write_cubagem_finalizada(self) -> None:
        self.write("CubagemFinalizada", REG_CUBAGEM_FINALIZADA, 1)

    def write_configs(self, velocidade_esteira: int) -> None:
        self.write("Config velocidade esteira", REG_VELOCIDADE_ESTEIRA, velocidade_esteira)
        self.write("Equipamento configurado", REG_EQUIPAMENTO_CONFIGURADO, 1)
