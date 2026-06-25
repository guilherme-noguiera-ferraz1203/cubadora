"""Múltiplos volumes por nota + totalização (porta de NotaVolume/ListNotaVolume/Multiplo/Totalizacao).

Modo "nota + volumes": escaneia-se "NOTA+3" para registrar 3 volumes da nota; cada cubagem
subsequente é um volume daquela nota até completar a quantidade.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

SEPARADOR = "+"


@dataclass
class NotaVolume:
    nota: str
    quantidade: int = 1
    volume_atual: int = 0

    def proximo_volume(self) -> int:
        self.volume_atual += 1
        return self.volume_atual

    def completa(self) -> bool:
        return self.volume_atual >= self.quantidade


class ListNotaVolume:
    """Gerencia a fila de notas e seus volumes (modo nota+volumes)."""

    def __init__(self) -> None:
        self.atual: NotaVolume | None = None
        self.historico: list[NotaVolume] = []

    def registrar_nota(self, texto: str) -> NotaVolume:
        """Processa 'NOTA+3' -> cria NotaVolume(nota='NOTA', quantidade=3)."""
        if SEPARADOR in texto:
            nota, _, q = texto.rpartition(SEPARADOR)
            quantidade = int("".join(c for c in q if c.isdigit()) or 1)
        else:
            nota, quantidade = texto, 1
        self.atual = NotaVolume(nota=nota.strip(), quantidade=quantidade)
        log.info("Nota registrada: %s (%d volumes)", self.atual.nota, self.atual.quantidade)
        return self.atual

    def process_etiqueta(self, texto: str, nota_mais_volumes: bool) -> str:
        """Retorna a etiqueta a usar na cubagem (porta de ListNotaVolume.processEtiqueta)."""
        if nota_mais_volumes and SEPARADOR in texto:
            self.registrar_nota(texto)
            return ""  # apenas registrou a nota; aguarda os volumes
        if nota_mais_volumes and self.atual and not self.atual.completa():
            n = self.atual.proximo_volume()
            etiqueta = f"{self.atual.nota}-{n}/{self.atual.quantidade}"
            if self.atual.completa():
                self.historico.append(self.atual)
            return etiqueta
        return texto


class Totalizacao:
    """Acumula volume e peso (porta de Totalizacao.java)."""

    def __init__(self) -> None:
        self.total_volume = 0.0
        self.total_peso = 0.0
        self.quantidade = 0

    def add(self, volume_m3: float, peso: float) -> None:
        self.total_volume += volume_m3
        self.total_peso += peso
        self.quantidade += 1

    def reset(self) -> None:
        self.total_volume = self.total_peso = 0.0
        self.quantidade = 0
