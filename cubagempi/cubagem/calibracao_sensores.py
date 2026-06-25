"""Assistente de calibração dos sensores de distância (calcula os fatores automaticamente).

A conversão é linear:  dimensão = aux - distância / fator.
Com DOIS objetos de tamanho conhecido (dois pontos), resolve-se fator e aux:

    fator = (d2 - d1) / (real1 - real2)
    aux   = real1 + d1 / fator

Onde (d, real) são (distância medida, dimensão real). Faz isso para altura, largura e
comprimento de uma vez (cada objeto fornece os três).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


def calibrar_por_cubo(distancias: dict, peso: float, cubo: dict, ajustes) -> tuple[dict, float, bool]:
    """Calibração por UM cubo conhecido (comando *cal*).

    Ajusta apenas os offsets (aux) de cada dimensão para que o cubo passe a ler exatamente as
    dimensões conhecidas, mantendo os fatores de escala (definidos no setup com 2 objetos).
    Também calcula o ajuste de peso. Retorna (novos_ajustes, ajuste_peso, ok).

    `distancias` = {altura, fundo, comprimento(=esq+dir)} em cm
    `cubo`       = {altura, largura, comprimento, peso} conhecidos
    `ajustes`    = ConfigAjustes atual (usa os fatores)
    """
    novos = {
        "aux_altura": round(cubo["altura"] + distancias["altura"] / ajustes.altura, 4),
        "aux_largura": round(cubo["largura"] + distancias["fundo"] / ajustes.largura, 4),
        "aux_comprimento": round(cubo["comprimento"] + distancias["comprimento"] / ajustes.comprimento, 4),
    }
    ajuste_peso = round(cubo["peso"] - peso, 3)
    ok = (distancias["altura"] > 0 and distancias["fundo"] > 0
          and distancias["comprimento"] > 0 and peso > 0)
    return novos, ajuste_peso, ok


@dataclass
class PontoCalibracao:
    # distâncias medidas (cm) usadas em cada fórmula
    dist_altura: float
    dist_fundo: float
    dist_comprimento: float      # = esquerda + direita
    # dimensões reais do objeto (cm)
    real_altura: float
    real_largura: float
    real_comprimento: float


@dataclass
class CalibracaoAssistente:
    pontos: list[PontoCalibracao] = field(default_factory=list)

    def limpar(self) -> None:
        self.pontos.clear()

    def capturar(self, distancias: dict, reais: dict) -> int:
        """Registra um ponto. `distancias`={altura,fundo,comprimento}; `reais`={altura,largura,comprimento}."""
        self.pontos.append(PontoCalibracao(
            dist_altura=float(distancias.get("altura", 0)),
            dist_fundo=float(distancias.get("fundo", 0)),
            dist_comprimento=float(distancias.get("comprimento", 0)),
            real_altura=float(reais.get("altura", 0)),
            real_largura=float(reais.get("largura", 0)),
            real_comprimento=float(reais.get("comprimento", 0)),
        ))
        return len(self.pontos)

    def pode_calcular(self) -> bool:
        return len(self.pontos) >= 2

    @staticmethod
    def _resolver(d1: float, r1: float, d2: float, r2: float) -> tuple[float, float] | None:
        if r1 == r2 or d1 == d2:
            return None
        fator = (d2 - d1) / (r1 - r2)
        if fator == 0:
            return None
        aux = r1 + d1 / fator
        return round(fator, 6), round(aux, 4)

    def calcular(self) -> dict:
        """Calcula os fatores propostos a partir do primeiro e do último ponto."""
        if not self.pode_calcular():
            raise ValueError("São necessários ao menos 2 pontos (2 objetos de tamanhos diferentes)")
        p1, p2 = self.pontos[0], self.pontos[-1]
        ajustes: dict = {}
        alt = self._resolver(p1.dist_altura, p1.real_altura, p2.dist_altura, p2.real_altura)
        lar = self._resolver(p1.dist_fundo, p1.real_largura, p2.dist_fundo, p2.real_largura)
        com = self._resolver(p1.dist_comprimento, p1.real_comprimento, p2.dist_comprimento, p2.real_comprimento)
        if alt:
            ajustes["altura"], ajustes["aux_altura"] = alt
        if lar:
            ajustes["largura"], ajustes["aux_largura"] = lar
        if com:
            ajustes["comprimento"], ajustes["aux_comprimento"] = com
        log.info("Calibração calculada: %s", ajustes)
        return ajustes
