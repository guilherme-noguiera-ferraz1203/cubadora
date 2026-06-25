"""Máquina ATM — cabine fechada com máquina de estados (porta de MaquinaAtm + AtmStates).

Fluxo: ocioso -> aguardando inserir objeto -> aguardando fechar porta -> posicionando ->
cubando -> aguardando retirar objeto -> ocioso. Mede altura (ultrassônico), L×C (câmera) e
peso (balança), igual à máquina câmera, mas disparado pelos sensores da cabine.
"""

from __future__ import annotations

import enum
import logging
import threading
import time

from ..config.models import AppConfig
from ..cubagem import Cubagem, altura_com_ajuste
from ..drivers.modbus import Modbus485, ModbusTimeout
from ..drivers.ultrasonic import IndexSensor
from .base import Cor, Maquina
from .hardware import Hardware

log = logging.getLogger(__name__)

LOOP_DELAY = 0.2


class AtmState(str, enum.Enum):
    OCIOSO = "ocioso"
    AGUARDANDO_INSERIR = "aguardando_inserir"
    AGUARDANDO_FECHAR_PORTA = "aguardando_fechar_porta"
    POSICIONANDO = "posicionando"
    CUBANDO = "cubando"
    AGUARDANDO_RETIRAR = "aguardando_retirar"


class AtmClp485:
    """Sensores da cabine via Modbus (porta de AtmClp485)."""

    def __init__(self, modbus: Modbus485, endereco: int, reg_porta: int, reg_objeto: int):
        self.modbus = modbus
        self.endereco = endereco
        self.reg_porta = reg_porta
        self.reg_objeto = reg_objeto

    def porta_fechada(self) -> bool:
        return self.modbus.read("Porta fechada", self.endereco, self.reg_porta) != 0

    def objeto_presente(self) -> bool:
        return self.modbus.read("Objeto presente", self.endereco, self.reg_objeto) != 0


class MaquinaAtm(Maquina):
    def __init__(self, hardware: Hardware, config: AppConfig):
        super().__init__()
        self.hw = hardware
        self.config = config
        self.estado = AtmState.OCIOSO
        self.atm_clp = AtmClp485(hardware.modbus, config.atm.endereco_clp,
                                 config.atm.registro_porta_fechada,
                                 config.atm.registro_objeto_presente)

    def _set_estado(self, estado: AtmState, cor: Cor, texto: str) -> None:
        self.estado = estado
        self.set_status(cor, texto)

    def _ler_altura(self) -> float:
        maior = 0.0
        for _ in range(self.config.sensor.leituras):
            try:
                dist = self.hw.sensor.read_sensor(int(IndexSensor.ALTURA))
                maior = max(maior, altura_com_ajuste(dist, self.config.ajustes))
            except Exception:  # noqa: BLE001
                pass
        return maior

    def ler_cubagem(self, etiqueta: str = "") -> Cubagem:
        """Mede o objeto na cabine (altura ultrassônico + L×C câmera + peso balança)."""
        cub = Cubagem(etiqueta=etiqueta)
        cub.altura = self._ler_altura()
        cub.largura, cub.comprimento = self.hw.camera.medir(etiqueta, cub.altura)
        try:
            cub.peso = self.hw.balanca.get_media_peso()
        except ModbusTimeout:
            cub.peso = 0.0
        self._notify_cubagem(cub)
        log.info("ATM %s", cub)
        return cub

    def simular_ciclo(self, etiqueta: str = "ATM") -> Cubagem:
        """Percorre os estados uma vez (para testes/simulação sem sensores reais)."""
        self._set_estado(AtmState.AGUARDANDO_INSERIR, Cor.AMARELO, "Insira o objeto")
        self._set_estado(AtmState.AGUARDANDO_FECHAR_PORTA, Cor.AMARELO, "Feche a porta")
        self._set_estado(AtmState.POSICIONANDO, Cor.AMARELO, "Posicionando")
        self._set_estado(AtmState.CUBANDO, Cor.AMARELO, "Cubando...")
        cub = self.ler_cubagem(etiqueta)
        self._set_estado(AtmState.AGUARDANDO_RETIRAR, Cor.VERDE, "Retire o objeto")
        self._set_estado(AtmState.OCIOSO, Cor.VERDE, "Pronto")
        return cub

    def run(self) -> None:
        self.running = True
        self.hw.init()
        self._set_estado(AtmState.OCIOSO, Cor.VERDE, "Pronto")
        log.info("MaquinaAtm em execução")
        while not self._stop.is_set():
            try:
                if self.estado == AtmState.OCIOSO:
                    if self.atm_clp.objeto_presente():
                        self._set_estado(AtmState.AGUARDANDO_FECHAR_PORTA, Cor.AMARELO, "Feche a porta")
                elif self.estado == AtmState.AGUARDANDO_FECHAR_PORTA:
                    if self.atm_clp.porta_fechada():
                        self._set_estado(AtmState.CUBANDO, Cor.AMARELO, "Cubando...")
                        self.ler_cubagem()
                        self._set_estado(AtmState.AGUARDANDO_RETIRAR, Cor.VERDE, "Retire o objeto")
                elif self.estado == AtmState.AGUARDANDO_RETIRAR:
                    if not self.atm_clp.objeto_presente():
                        self._set_estado(AtmState.OCIOSO, Cor.VERDE, "Pronto")
            except ModbusTimeout:
                self.set_status(Cor.VERMELHO, "Cabine sem comunicação")
            except Exception:  # noqa: BLE001
                log.exception("Erro no loop da ATM")
            time.sleep(LOOP_DELAY)
