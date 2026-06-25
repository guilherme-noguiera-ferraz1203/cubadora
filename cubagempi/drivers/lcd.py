"""Display LCD 16x2 (porta de Lcd/Lcd16x2/LcdNull).

- LcdNull : sem display (no-op)
- MockLcd : guarda as linhas (PC/testes)
- LcdI2C16x2 : HD44780 via expansor I²C PCF8574 (endereço típico 0x27) no Raspberry Pi
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from ..config.models import ConfigLcd

log = logging.getLogger(__name__)


class Lcd(ABC):
    @abstractmethod
    def init(self) -> None: ...
    @abstractmethod
    def clear(self) -> None: ...
    @abstractmethod
    def write_line(self, linha: int, texto: str) -> None: ...


class LcdNull(Lcd):
    def init(self) -> None: ...
    def clear(self) -> None: ...
    def write_line(self, linha: int, texto: str) -> None: ...


class MockLcd(Lcd):
    def __init__(self) -> None:
        self.linhas = ["", ""]

    def init(self) -> None:
        self.linhas = ["", ""]

    def clear(self) -> None:
        self.linhas = ["", ""]

    def write_line(self, linha: int, texto: str) -> None:
        if 0 <= linha < 2:
            self.linhas[linha] = texto[:16]


class LcdI2C16x2(Lcd):
    """HD44780 16x2 via PCF8574 (backpack I²C). Modo 4 bits."""

    LCD_CHR = 1
    LCD_CMD = 0
    LINE = (0x80, 0xC0)
    BACKLIGHT = 0x08
    EN = 0b00000100

    def __init__(self, config: ConfigLcd):
        from smbus2 import SMBus
        self.addr = config.i2c_address
        self.bus = SMBus(config.i2c_bus)
        self.init()

    def _strobe(self, data: int) -> None:
        self.bus.write_byte(self.addr, data | self.EN | self.BACKLIGHT)
        time.sleep(0.0005)
        self.bus.write_byte(self.addr, (data & ~self.EN) | self.BACKLIGHT)
        time.sleep(0.0001)

    def _write4(self, data: int) -> None:
        self.bus.write_byte(self.addr, data | self.BACKLIGHT)
        self._strobe(data)

    def _write(self, byte: int, mode: int) -> None:
        self._write4(mode | (byte & 0xF0))
        self._write4(mode | ((byte << 4) & 0xF0))

    def init(self) -> None:
        for cmd in (0x33, 0x32, 0x06, 0x0C, 0x28, 0x01):
            self._write(cmd, self.LCD_CMD)
        time.sleep(0.005)

    def clear(self) -> None:
        self._write(0x01, self.LCD_CMD)
        time.sleep(0.005)

    def write_line(self, linha: int, texto: str) -> None:
        if not (0 <= linha < 2):
            return
        self._write(self.LINE[linha], self.LCD_CMD)
        for ch in texto.ljust(16)[:16]:
            self._write(ord(ch), self.LCD_CHR)


def create_lcd(config: ConfigLcd, simulado: bool = False) -> Lcd:
    modelo = (config.modelo or "NENHUM").upper()
    if modelo == "NENHUM":
        return MockLcd() if simulado else LcdNull()
    if simulado:
        return MockLcd()
    try:
        if modelo == "I2C_16X2":
            return LcdI2C16x2(config)
    except Exception as exc:  # noqa: BLE001
        log.warning("LCD indisponível (%s); usando LcdNull", exc)
    return LcdNull()


class LcdView:
    """Atualiza o LCD com status e última cubagem."""

    def __init__(self, lcd: Lcd):
        self.lcd = lcd

    def on_status(self, status) -> None:
        self.lcd.write_line(0, status.texto)

    def on_cubagem(self, cub) -> None:
        self.lcd.write_line(0, f"A{cub.altura:.0f} L{cub.largura:.0f} C{cub.comprimento:.0f}")
        self.lcd.write_line(1, f"P{cub.peso:.2f}kg V{cub.volume_m3:.3f}")
