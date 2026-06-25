"""Máquina dinâmica/CLP (porta simplificada de MaquinaDinamicaClp.java).

Esteira controlada por CLP via Modbus. Loop: aguarda peso disponível -> mede (peso Modbus,
altura ultrassônico, L×C câmera) -> valida -> libera caixa. A balança é Modbus (Balanca485).
"""

from __future__ import annotations

import logging
import threading
import time

from ..config.models import AppConfig
from ..cubagem import Cubagem, altura_com_ajuste
from ..drivers.modbus import ModbusTimeout
from ..drivers.ultrasonic import IndexSensor
from .base import Cor, Maquina
from .hardware import Hardware

log = logging.getLogger(__name__)

LOOP_DELAY = 0.2


class MaquinaDinamica(Maquina):
    def __init__(self, hardware: Hardware, config: AppConfig):
        super().__init__()
        self.hw = hardware
        self.config = config

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
        """Uma medição da esteira: peso (Modbus) + altura (ultrassônico) + L×C (câmera)."""
        cub = Cubagem(etiqueta=etiqueta)
        try:
            cub.peso = self.hw.balanca.get_media_peso()
        except ModbusTimeout:
            log.warning("Timeout ao ler peso da balança Modbus")
        cub.altura = self._ler_altura()
        cub.largura, cub.comprimento = self.hw.camera.medir(etiqueta, cub.altura)
        self._notify_cubagem(cub)
        log.info("%s", cub)
        return cub

    def _validar(self, cub: Cubagem) -> bool:
        d = self.config.dinamica
        return (d.altura_min <= cub.altura <= d.altura_max
                and d.largura_min <= cub.largura <= d.largura_max
                and d.comprimento_min <= cub.comprimento <= d.comprimento_max
                and d.peso_min <= cub.peso <= d.peso_max)

    def run(self) -> None:
        self.running = True
        self.hw.init()
        try:
            self.hw.clp.write_configs(self.config.dinamica.velocidade_esteira)
        except Exception:  # noqa: BLE001
            log.exception("Erro ao configurar o CLP")
        log.info("MaquinaDinamica em execução")

        while not self._stop.is_set():
            try:
                if self.hw.clp.is_emergencia():
                    self.set_status(Cor.VERMELHO, "Emergência")
                    time.sleep(LOOP_DELAY)
                    continue
                if self.hw.clp.is_peso_disponivel():
                    self.set_status(Cor.AMARELO, "Cubando...")
                    cub = self.ler_cubagem()
                    self.hw.clp.zerar_nova_pesagem()
                    if self._validar(cub):
                        self.set_status(Cor.VERDE, "OK")
                        self.hw.clp.write_liberar_caixa()
                    else:
                        self.set_status(Cor.VERMELHO, "Fora dos limites")
                        self.hw.clp.write_parar_esteira()
                    self.hw.clp.write_cubagem_finalizada()
            except ModbusTimeout:
                self.set_status(Cor.VERMELHO, "CLP sem comunicação")
            except Exception:  # noqa: BLE001
                log.exception("Erro no loop da esteira")
            time.sleep(LOOP_DELAY)
