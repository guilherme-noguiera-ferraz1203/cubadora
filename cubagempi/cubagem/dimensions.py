"""Conversão das distâncias dos sensores (cm) em dimensões reais (cm).

Fórmulas idênticas ao Config.java:
  altura      = max(0, aux_altura      - dist_altura            / f_altura)
  largura     = max(0, aux_largura     - dist_fundo             / f_largura)
  comprimento = max(0, aux_comprimento - (dist_esq + dist_dir)  / f_comprimento)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..config.models import ConfigAjustes

log = logging.getLogger(__name__)


def altura_com_ajuste(dist: Optional[float], aj: ConfigAjustes) -> float:
    if dist is not None and dist > 0:
        return max(0.0, aj.aux_altura - dist / aj.altura)
    return 0.0


def largura_com_ajuste(dist: Optional[float], aj: ConfigAjustes) -> float:
    if dist is not None and dist > 0:
        return max(0.0, aj.aux_largura - dist / aj.largura)
    return 0.0


def comprimento_com_ajuste(dist1: Optional[float], dist2: Optional[float], aj: ConfigAjustes) -> float:
    """Comprimento a partir dos dois sensores laterais (esquerda + direita)."""
    if dist1 and dist2 and dist1 > 0 and dist2 > 0:
        return max(0.0, aj.aux_comprimento - (dist1 + dist2) / aj.comprimento)
    log.warning("Pelo menos um dos sensores de comprimento está zerado.")
    return 0.0


@dataclass
class Cubagem:
    altura: float = 0.0
    largura: float = 0.0
    comprimento: float = 0.0
    peso: float = 0.0
    etiqueta: str = ""

    @property
    def volume_m3(self) -> float:
        return (self.altura * self.largura * self.comprimento) / 1_000_000.0

    def is_empty(self) -> bool:
        """Algum parâmetro zerado/negativo (equivalente a isAnyEmpty do Java)."""
        return (self.altura <= 0 or self.largura <= 0
                or self.comprimento <= 0 or self.peso <= 0)

    def to_dict(self) -> dict:
        return {
            "etiqueta": self.etiqueta,
            "altura": round(self.altura, 2),
            "largura": round(self.largura, 2),
            "comprimento": round(self.comprimento, 2),
            "peso": round(self.peso, 3),
            "volume_m3": round(self.volume_m3, 4),
        }

    def __str__(self) -> str:
        return (f"Cubagem[{self.etiqueta or '-'}: "
                f"A={self.altura:.1f} L={self.largura:.1f} C={self.comprimento:.1f} cm, "
                f"P={self.peso:.3f} kg, V={self.volume_m3:.4f} m³]")
