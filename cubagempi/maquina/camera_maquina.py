"""Máquina com câmera (porta simplificada de MaquinaCamera.java).

Altura vem dos sensores ultrassônicos; largura e comprimento vêm da câmera (foto top-down).
"""

from __future__ import annotations

import logging
import threading
import time

from ..config.models import AppConfig
from ..cubagem import Cubagem, altura_com_ajuste
from ..drivers.ultrasonic import IndexSensor
from .base import Cor, Maquina
from .hardware import Hardware

log = logging.getLogger(__name__)


class MaquinaCamera(Maquina):
    def __init__(self, hardware: Hardware, config: AppConfig):
        super().__init__()
        self.hw = hardware
        self.config = config

    def _ler_altura(self, leituras: int = 10) -> float:
        """Lê o sensor de altura várias vezes e usa a maior medida (como no Java)."""
        maior = 0.0
        for _ in range(leituras):
            try:
                dist = self.hw.sensor.read_sensor(int(IndexSensor.ALTURA))
                altura = altura_com_ajuste(dist, self.config.ajustes)
                maior = max(maior, altura)
            except Exception:  # noqa: BLE001
                log.exception("Erro ao ler altura")
            time.sleep(self.config.sensor.delay_sensores_ms / 1000.0)
        return maior

    def ler_cubagem(self, etiqueta: str = "") -> Cubagem:
        self.set_status(Cor.AMARELO, "Medindo...")

        peso_holder: dict[str, float] = {"peso": 0.0}

        def ler_peso() -> None:
            try:
                peso_holder["peso"] = self.hw.balanca.get_media_peso()
            except Exception:  # noqa: BLE001
                peso_holder["peso"] = 0.0

        t = threading.Thread(target=ler_peso, name="balanca")
        t.start()

        cub = Cubagem(etiqueta=etiqueta)
        cub.altura = self._ler_altura()
        cub.largura, cub.comprimento = self.hw.camera.medir(etiqueta, cub.altura)

        t.join()
        cub.peso = peso_holder["peso"]

        self._notify_cubagem(cub)
        self.set_status(Cor.VERDE, "OK")
        log.info("%s", cub)
        return cub

    def run(self) -> None:
        self.running = True
        self.hw.init()
        log.info("MaquinaCamera em execução")
