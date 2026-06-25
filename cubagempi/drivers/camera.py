"""Driver de câmera (modelos CAMERA/dinâmico/ATM).

A câmera fotografa a caixa de cima e a análise de imagem (vision.BoxAnalyzer) calcula
largura x comprimento, usando a altura (perspectiva) medida pelos ultrassônicos.
- MockCamera     : devolve medidas configuradas (PC/testes)
- Picamera2Camera: captura real no Pi (picamera2) + análise OpenCV
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config.models import ConfigCamera

log = logging.getLogger(__name__)


class Camera(ABC):
    @abstractmethod
    def medir(self, etiqueta: str, altura_cm: float = 0.0) -> tuple[float, float]:
        """Retorna (largura_cm, comprimento_cm)."""

    def close(self) -> None:  # opcional
        pass


class MockCamera(Camera):
    def __init__(self, config: ConfigCamera):
        self.config = config

    def medir(self, etiqueta: str, altura_cm: float = 0.0) -> tuple[float, float]:
        return self.config.largura_simulada, self.config.comprimento_simulado


class Picamera2Camera(Camera):
    """Captura real no Raspberry Pi + análise via vision.BoxAnalyzer."""

    def __init__(self, config: ConfigCamera):
        from picamera2 import Picamera2  # import tardio: só existe no Pi
        from ..vision import BoxAnalyzer

        self.config = config
        self.analyzer = BoxAnalyzer(config)
        self._cam = Picamera2()
        self._cam.configure(self._cam.create_still_configuration())
        self._cam.start()

    def _capturar(self, etiqueta: str) -> str:
        arquivo = self.config.arquivo.replace("$etiqueta", etiqueta)
        self._cam.capture_file(arquivo)
        return arquivo

    def medir(self, etiqueta: str, altura_cm: float = 0.0) -> tuple[float, float]:
        arquivo = self._capturar(etiqueta)
        largura, comprimento, _ = self.analyzer.analyze(arquivo, altura_cm)
        if largura <= 0 or comprimento <= 0:
            log.warning("Análise não encontrou a caixa; usando medidas de fallback")
            return self.config.largura_simulada, self.config.comprimento_simulado
        return largura, comprimento

    def close(self) -> None:
        try:
            self._cam.stop()
        except Exception:  # noqa: BLE001
            pass


def create_camera(config: ConfigCamera, simulado: bool) -> Camera:
    if simulado or not config.habilitada:
        return MockCamera(config)
    try:
        return Picamera2Camera(config)
    except Exception as exc:  # noqa: BLE001
        log.warning("Câmera real indisponível (%s); usando MockCamera", exc)
        return MockCamera(config)
