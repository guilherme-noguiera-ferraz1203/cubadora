"""Abstração de barramento I²C (ponte ATmega).

Operações cruas (não baseadas em registrador), como o sistema Java faz:
- write_byte(addr, value): escreve 1 byte (seleciona o "device/comando" do ATmega)
- read_bytes(addr, n):     lê n bytes da resposta
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Protocol

log = logging.getLogger(__name__)

# Handler do simulador: recebe (device, length) e devolve os bytes lidos.
DeviceHandler = Callable[[int, int], bytes]


class I2CBus(Protocol):
    def write_byte(self, addr: int, value: int) -> None: ...
    def read_bytes(self, addr: int, length: int) -> bytes: ...
    def close(self) -> None: ...


class Smbus2I2C:
    """I²C real no Raspberry Pi via smbus2 (transferências cruas i2c_rdwr)."""

    def __init__(self, bus: int = 1) -> None:
        from smbus2 import SMBus  # import tardio: só existe no Pi

        self._smbus_mod = __import__("smbus2", fromlist=["i2c_msg"])
        self._bus = SMBus(bus)

    def write_byte(self, addr: int, value: int) -> None:
        msg = self._smbus_mod.i2c_msg.write(addr, [value & 0xFF])
        self._bus.i2c_rdwr(msg)

    def read_bytes(self, addr: int, length: int) -> bytes:
        msg = self._smbus_mod.i2c_msg.read(addr, length)
        self._bus.i2c_rdwr(msg)
        return bytes(list(msg))

    def close(self) -> None:
        self._bus.close()


class MockI2C:
    """I²C simulado: lembra o último 'device' escrito e responde via handler."""

    def __init__(self, handler: Optional[DeviceHandler] = None) -> None:
        self._handler = handler or (lambda dev, n: bytes(n))
        self._last_device = 0

    def set_handler(self, handler: DeviceHandler) -> None:
        self._handler = handler

    def write_byte(self, addr: int, value: int) -> None:
        self._last_device = value & 0xFF

    def read_bytes(self, addr: int, length: int) -> bytes:
        data = self._handler(self._last_device, length)
        # garante o tamanho solicitado
        if len(data) < length:
            data = data + bytes(length - len(data))
        return data[:length]

    def close(self) -> None:
        pass


def create_i2c(bus: int = 1, handler: Optional[DeviceHandler] = None, real: bool | None = None) -> I2CBus:
    if handler is not None and real is not True:
        return MockI2C(handler)
    try:
        return Smbus2I2C(bus)
    except Exception as exc:  # noqa: BLE001
        if real is True:
            raise
        log.warning("I²C real indisponível (%s); usando MockI2C", exc)
        return MockI2C(handler)
