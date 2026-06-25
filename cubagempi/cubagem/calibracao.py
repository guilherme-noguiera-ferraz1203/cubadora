"""Aferição/calibração (porta de Calibracao.java).

NÃO calcula os fatores de ajuste: é uma VERIFICAÇÃO de que o objeto-padrão (com dimensões e
peso conhecidos no config) foi medido dentro da tolerância. Enquanto não aferida, a máquina
não aceita cubagens reais — a primeira medição serve para conferir a aferição.
"""

from __future__ import annotations

import logging

from ..config.models import ConfigCalibracao
from .dimensions import Cubagem

log = logging.getLogger(__name__)


class Calibracao:
    def __init__(self, config: ConfigCalibracao, modo_teste: bool = False):
        self.config = config
        self.modo_teste = modo_teste
        self.calibrado_altura = False
        self.calibrado_largura = False
        self.calibrado_comprimento = False
        self.calibrado_peso = False

    def _calibrar_valor(self, valor: float | None) -> None:
        if valor is None:
            return
        r = self.config.range_sensor
        if abs(valor - self.config.altura) <= r and not self.calibrado_altura:
            self.calibrado_altura = True
        elif abs(valor - self.config.largura) <= r and not self.calibrado_largura:
            self.calibrado_largura = True
        elif abs(valor - self.config.comprimento) <= r and not self.calibrado_comprimento:
            self.calibrado_comprimento = True

    def calibrar(self, cub: Cubagem) -> bool:
        log.info("Aferição início: A=%.2f L=%.2f C=%.2f P=%.2f",
                 cub.altura, cub.largura, cub.comprimento, cub.peso)
        self.calibrado_altura = self.calibrado_largura = False
        self.calibrado_comprimento = self.calibrado_peso = False
        for valor in (cub.altura, cub.largura, cub.comprimento):
            self._calibrar_valor(valor)
        if abs(cub.peso - self.config.peso) <= self.config.range_peso:
            self.calibrado_peso = True
        log.info("Aferição resultado: A=%s L=%s C=%s P=%s",
                 self.calibrado_altura, self.calibrado_largura,
                 self.calibrado_comprimento, self.calibrado_peso)
        return self.is_calibrado()

    def set_calibrado(self, valor: bool = True) -> None:
        """Marca a máquina como aferida (usado após a calibração pelo cubo, *cal*)."""
        self.calibrado_altura = valor
        self.calibrado_largura = valor
        self.calibrado_comprimento = valor
        self.calibrado_peso = valor

    def is_calibrado(self) -> bool:
        return self.modo_teste or (self.calibrado_altura and self.calibrado_largura
                                   and self.calibrado_comprimento and self.calibrado_peso)

    def is_not_calibrado(self) -> bool:
        return not self.is_calibrado()
