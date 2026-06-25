"""Responder combinado para o barramento RS-485 simulado.

O mesmo barramento carrega frames do ultrassônico (5 bytes) e do Modbus (>= 8 bytes).
Dispatcher por tamanho do frame.
"""

from __future__ import annotations

from typing import Optional

from .modbus_sim import ModbusSimulator
from .ultrasonic_sim import UltrasonicSimulator


def combined_responder(ultra: UltrasonicSimulator, modbus: ModbusSimulator):
    def responder(tx: bytes, length_rx: int) -> Optional[bytes]:
        if len(tx) == 5:
            return ultra.responder(tx, length_rx)
        if len(tx) >= 8:
            return modbus.responder(tx, length_rx)
        return None
    return responder
