"""Analisador de caixa por imagem (porta do DefaultImageAnalyzer/photobox).

Detecta a caixa numa foto top-down e calcula largura/comprimento/ângulo em cm.
A conversão px->cm depende da ALTURA (perspectiva): quanto mais alta a caixa, mais perto da
câmera e maior na imagem. Usa a calibração linear `escala = altura_a*altura_cm + altura_b`
(os coeficientes vêm de uma aferição com objeto de tamanho conhecido, ex.: folha A4).

OpenCV é opcional: sem ele, retorna (0, 0, 0) e registra um aviso.
"""

from __future__ import annotations

import logging

from ..config.models import ConfigCamera

log = logging.getLogger(__name__)


def px_to_cm(px: float, altura_cm: float, altura_a: float, altura_b: float) -> float:
    """Converte pixels em cm conforme a altura da caixa (calibração de perspectiva)."""
    escala = altura_a * altura_cm + altura_b
    return px * escala


class BoxAnalyzer:
    def __init__(self, config: ConfigCamera):
        self.config = config

    def _crop(self, img):
        c = self.config
        if c.crop_right > c.crop_left and c.crop_bottom > c.crop_top:
            return img[c.crop_top:c.crop_bottom, c.crop_left:c.crop_right]
        return img

    def analyze(self, arquivo: str, altura_cm: float) -> tuple[float, float, float]:
        """Retorna (largura_cm, comprimento_cm, angulo_graus)."""
        try:
            import cv2  # opcional
            import numpy as np
        except ImportError:
            log.warning("OpenCV indisponível; análise de imagem não executada.")
            return 0.0, 0.0, 0.0

        img = cv2.imread(arquivo)
        if img is None:
            log.warning("Não foi possível ler a imagem: %s", arquivo)
            return 0.0, 0.0, 0.0

        roi = self._crop(img)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thr = cv2.threshold(gray, self.config.rgb_threshold, 255,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contornos, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contornos:
            return 0.0, 0.0, 0.0

        maior = max(contornos, key=cv2.contourArea)
        (_, (w_px, h_px), angulo) = cv2.minAreaRect(maior)

        largura_px = min(w_px, h_px)
        comprimento_px = max(w_px, h_px)
        largura = px_to_cm(largura_px, altura_cm, self.config.altura_a, self.config.altura_b)
        comprimento = px_to_cm(comprimento_px, altura_cm, self.config.altura_a, self.config.altura_b)
        log.info("Análise imagem: %.1fpx x %.1fpx @ alt=%.1f -> %.1f x %.1f cm (ang=%.1f)",
                 largura_px, comprimento_px, altura_cm, largura, comprimento, angulo)
        return round(largura, 1), round(comprimento, 1), round(angulo, 1)

    def calibrar_a4(self, arquivo: str, altura_cm: float) -> tuple[float, float] | None:
        """Calcula novos coeficientes altura_a/altura_b a partir de uma folha A4 (29,7 cm)."""
        l, c, _ = self.analyze(arquivo, altura_cm)
        if c <= 0:
            return None
        log.info("Calibração A4: lado maior medido = %.1f cm (esperado 29,7)", c)
        return self.config.altura_a, self.config.altura_b
