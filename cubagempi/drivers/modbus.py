"""Modbus RTU sobre o barramento RS-485 (porta de ModbusRTU.java + Modbus485.java).

Usado pela balança dinâmica (endereço 2) e pelo CLP (endereço 1).
Funções: 3 = leitura, 6 = escrita, 16 = escrita múltipla. CRC-16 (poly 0xA001).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from ..hal.rs485 import Rs485
from .checksum import modbus_crc

log = logging.getLogger(__name__)

FUNCAO_LEITURA = 3
FUNCAO_ESCRITA = 6
FUNCAO_ESCRITA_MULTIPLA = 16
TENTATIVAS = 10


class ModbusTimeout(Exception):
    pass


def build_frame(endereco: int, funcao: int, registro: int, valor: int) -> bytes:
    buf = bytearray(8)
    buf[0] = endereco & 0xFF
    buf[1] = funcao & 0xFF
    buf[2] = (registro // 256) & 0xFF
    buf[3] = (registro % 256) & 0xFF
    buf[4] = (valor // 256) & 0xFF
    buf[5] = (valor % 256) & 0xFF
    crc = modbus_crc(bytes(buf[0:6]))
    buf[6] = crc % 256
    buf[7] = crc // 256
    return bytes(buf)


def rx_length(frame_tx: bytes) -> int:
    funcao = frame_tx[1]
    if funcao == FUNCAO_ESCRITA:
        return 8
    count = frame_tx[4] * 256 + frame_tx[5]
    return count * 2 + 5


def is_crc_ok(buffer: bytes) -> bool:
    if buffer is None or len(buffer) < 2:
        return False
    crc = modbus_crc(buffer[:-2])
    return buffer[-2] == (crc % 256) and buffer[-1] == (crc // 256)


class Modbus485:
    def __init__(self, rs485: Rs485):
        self.rs485 = rs485

    def _transacao(self, name: str, frame_tx: bytes, length_rx: int) -> bytes:
        for _ in range(TENTATIVAS):
            try:
                rx = self.rs485.write(frame_tx, length_rx)
                if rx is None:
                    continue
                if is_crc_ok(rx):
                    return rx
                log.debug("Modbus485 erro de CRC (%s)", name)
                time.sleep(0.01)
            except Exception:  # noqa: BLE001
                log.exception("Modbus485 erro no envio (%s)", name)
        raise ModbusTimeout(name)

    def read(self, name: str, endereco: int, registro: int) -> int:
        frame = build_frame(endereco, FUNCAO_LEITURA, registro, 1)
        rx = self._transacao(name, frame, rx_length(frame))
        valor = rx[3] * 256 + rx[4]
        if valor >= 0x8000:        # short com sinal
            valor -= 0x10000
        return valor

    def write(self, name: str, endereco: int, registro: int, valor: int) -> None:
        frame = build_frame(endereco, FUNCAO_ESCRITA, registro, valor & 0xFFFF)
        self._transacao(name, frame, rx_length(frame))

    def read_string(self, name: str, endereco: int, registro: int, tamanho: int) -> str:
        frame = build_frame(endereco, FUNCAO_LEITURA, registro, tamanho)
        rx = self._transacao(name, frame, rx_length(frame))
        chars: list[str] = []
        fim = len(rx) - 2
        i = 3
        while i < fim:
            if i + 1 < fim:
                if rx[i + 1] < 32:
                    break
                chars.append(chr(rx[i + 1]))
            if rx[i] < 32:
                break
            chars.append(chr(rx[i]))
            i += 2
        return "".join(chars)
