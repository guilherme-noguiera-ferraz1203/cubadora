"""Protocolos das balanças seriais (Trentin e Weightech) + buffer delimitado.

Porta de Trentin.java, Weightech.java e DelimitedBuffer.java.
Os bytes do peso vêm em ASCII entre um byte de início (estado) e o byte de parada.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


class Trentin:
    BAUD_RATE = 9600
    TAMANHO = 8
    START_PESANDO = 64        # '@'
    START_ESTABILIZADO = 68   # 'D'
    START_ZERADO = 70         # 'F'
    START_NEGATIVO = 76       # 'L'
    START_BYTES = (64, 68, 70, 76)
    STOP_BYTE = 13            # '\r'

    @staticmethod
    def is_start_byte(value: int) -> bool:
        return value in Trentin.START_BYTES

    @staticmethod
    def exists_peso(buf: list[int], i: int) -> bool:
        return (Trentin.is_start_byte(buf[i]) and len(buf) >= i + Trentin.TAMANHO
                and buf[i + Trentin.TAMANHO - 1] == Trentin.STOP_BYTE)

    @staticmethod
    def parse_peso(buf: list[int], i: int) -> float:
        s = "".join(chr(buf[j]) for j in range(i + 1, i + Trentin.TAMANHO - 1))
        return float(s)


class Weightech:
    TAMANHO = 9
    START_BYTES = (43, 45)    # '+', '-'
    STOP_BYTE = 107           # 'k'

    @staticmethod
    def is_start_byte(value: int) -> bool:
        return value in Weightech.START_BYTES

    @staticmethod
    def exists_peso(buf: list[int], i: int) -> bool:
        return (Weightech.is_start_byte(buf[i]) and len(buf) >= i + Weightech.TAMANHO
                and buf[i + Weightech.TAMANHO - 1] == Weightech.STOP_BYTE)

    @staticmethod
    def parse_peso(buf: list[int], i: int) -> float:
        s = "".join(chr(buf[j]) for j in range(i + 1, i + Weightech.TAMANHO - 1))
        return float(s)


class DelimitedBuffer:
    """Acumula bytes e extrai pacotes entre start_bytes e stop_byte (porta de DelimitedBuffer.java)."""

    def __init__(self, start_bytes: tuple[int, ...], stop_byte: int, remove_delimiters: bool = False):
        self.start_bytes = start_bytes
        self.stop_byte = stop_byte
        self.remove_delimiters = remove_delimiters
        self.buffer: list[int] = []

    def clear(self) -> None:
        self.buffer = []

    def _index_of(self, value: int, start: int) -> int:
        for i in range(start, len(self.buffer)):
            if self.buffer[i] == value:
                return i
        return -1

    def _index_of_start(self) -> int:
        for sb in self.start_bytes:
            idx = self._index_of(sb, 0)
            if idx != -1:
                return idx
        return -1

    def process(self, buffer_new: Optional[list[int]]) -> Optional[list[int]]:
        if buffer_new:
            self.buffer.extend(buffer_new)
        result = None
        i_start = self._index_of_start()
        if i_start != -1:
            i_stop = self._index_of(self.stop_byte, i_start + 1)
            if i_stop != -1:
                if self.remove_delimiters:
                    result = self.buffer[i_start + 1:i_stop]
                else:
                    result = self.buffer[i_start:i_stop + 1]
                self.buffer = self.buffer[i_stop + 1:]
        return result
