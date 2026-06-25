"""Abstração de pino GPIO de saída (LED, linha DE do RS-485, luz, etc.)."""

from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class OutputPin(Protocol):
    def high(self) -> None: ...
    def low(self) -> None: ...
    def toggle(self) -> None: ...
    def close(self) -> None: ...


class MockOutputPin:
    """Pino simulado: apenas guarda o estado (para PC/testes)."""

    def __init__(self, bcm: int, initial: bool = False) -> None:
        self.bcm = bcm
        self.state = initial

    def high(self) -> None:
        self.state = True

    def low(self) -> None:
        self.state = False

    def toggle(self) -> None:
        self.state = not self.state

    def close(self) -> None:
        self.state = False


class GpiozeroOutputPin:
    """Pino real no Raspberry Pi via gpiozero."""

    def __init__(self, bcm: int, initial: bool = False) -> None:
        from gpiozero import LED  # import tardio: só existe no Pi

        self.bcm = bcm
        self._led = LED(bcm, initial_value=initial)

    def high(self) -> None:
        self._led.on()

    def low(self) -> None:
        self._led.off()

    def toggle(self) -> None:
        self._led.toggle()

    def close(self) -> None:
        self._led.close()


def create_output_pin(bcm: int, initial: bool = False, real: bool | None = None) -> OutputPin:
    """Cria um pino real (Pi) ou mock (PC).

    real=None -> autodetecta: tenta gpiozero, cai para mock se indisponível.
    """
    if real is False:
        return MockOutputPin(bcm, initial)
    try:
        return GpiozeroOutputPin(bcm, initial)
    except Exception as exc:  # noqa: BLE001 - qualquer falha => mock
        if real is True:
            raise
        log.debug("gpiozero indisponível (%s); usando MockOutputPin para BCM%s", exc, bcm)
        return MockOutputPin(bcm, initial)
