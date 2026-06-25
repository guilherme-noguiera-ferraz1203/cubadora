"""Simulador de dispositivos Modbus RTU no barramento RS-485 (balança dinâmica + CLP).

Mantém um conjunto de registradores por endereço e responde a leitura (3) e escrita (6).
"""

from __future__ import annotations

from typing import Optional

from ..drivers.checksum import modbus_crc


class ModbusSimulator:
    def __init__(self, registros: dict[tuple[int, int], int] | None = None):
        # chave = (endereco, registro) -> valor
        self.registros: dict[tuple[int, int], int] = registros or {}

    def set(self, endereco: int, registro: int, valor: int) -> None:
        self.registros[(endereco, registro)] = valor & 0xFFFF

    def get(self, endereco: int, registro: int) -> int:
        return self.registros.get((endereco, registro), 0)

    def _frame(self, payload: list[int]) -> bytes:
        crc = modbus_crc(bytes(payload))
        return bytes(payload + [crc % 256, crc // 256])

    def responder(self, tx: bytes, length_rx: int) -> Optional[bytes]:
        if len(tx) < 8:
            return None
        endereco, funcao = tx[0], tx[1]
        registro = tx[2] * 256 + tx[3]
        arg = tx[4] * 256 + tx[5]

        if funcao == 3:  # leitura de `arg` registradores a partir de `registro`
            count = arg
            payload = [endereco, funcao, count * 2]
            for i in range(count):
                valor = self.get(endereco, registro + i)
                payload += [(valor // 256) & 0xFF, valor % 256]
            return self._frame(payload)

        if funcao == 6:  # escrita de 1 registrador
            self.set(endereco, registro, arg)
            return self._frame([endereco, funcao, tx[2], tx[3], tx[4], tx[5]])

        return None
