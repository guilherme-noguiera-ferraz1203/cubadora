"""Máquina estática (porta de MaquinaEstatica.java).

Estação fixa: lê a balança (em paralelo) e os sensores ultrassônicos, converte em
dimensões e valida a faixa. Modelo desta instalação (ESTATICA_2).
"""

from __future__ import annotations

import logging
import threading

from ..config.models import AppConfig
from ..cubagem import Cubagem, altura_com_ajuste, comprimento_com_ajuste, largura_com_ajuste
from ..drivers.ultrasonic import IndexSensor, SensorOutOfRangeError
from .base import Cor, Maquina
from .hardware import Hardware

log = logging.getLogger(__name__)


class MaquinaEstatica(Maquina):
    def __init__(self, hardware: Hardware, config: AppConfig):
        super().__init__()
        self.hw = hardware
        self.config = config

    def ler_cubagem(self, etiqueta: str = "") -> Cubagem:
        self.set_status(Cor.AMARELO, "Medindo...")

        # Balança em paralelo (thread), como no Java (BalancaWorker).
        peso_holder: dict[str, float] = {"peso": 0.0}

        def ler_peso() -> None:
            try:
                peso_holder["peso"] = self.hw.balanca.get_media_peso()
            except Exception:  # noqa: BLE001
                log.exception("Erro ao ler peso")
                peso_holder["peso"] = 0.0

        t = threading.Thread(target=ler_peso, name="balanca")
        t.start()

        medidas = self.hw.sensor.ler_sensores()
        aj = self.config.ajustes
        cub = Cubagem(etiqueta=etiqueta)
        cub.altura = altura_com_ajuste(medidas.get(IndexSensor.ALTURA), aj)
        cub.largura = largura_com_ajuste(medidas.get(IndexSensor.FUNDO), aj)
        cub.comprimento = comprimento_com_ajuste(
            medidas.get(IndexSensor.ESQUERDA), medidas.get(IndexSensor.DIREITA), aj
        )

        t.join()
        cub.peso = peso_holder["peso"]

        self._notify_cubagem(cub)
        if self.hw.sensor.is_out_of_range(medidas):
            self.set_status(Cor.VERMELHO, "Altere a posição da caixa e tente novamente")
            raise SensorOutOfRangeError()

        self.set_status(Cor.VERDE, "OK")
        log.info("%s", cub)
        return cub

    def run(self) -> None:
        self.running = True
        self.hw.init()
        log.info("MaquinaEstatica em execução")
