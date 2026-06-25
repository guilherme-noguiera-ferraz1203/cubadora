"""Checksums dos protocolos.

- Ultrassônico (proprietário): soma simples com constante 1234.
- Modbus RTU: CRC-16 (polinômio 0xA001, init 0xFFFF) — para as fases de CLP/balança Modbus.
"""

from __future__ import annotations

ULTRASONIC_CHECKSUM_CONST = 1234


def ultrasonic_checksum(address: int, data_msb: int, data_lsb: int) -> int:
    """Checksum do frame ultrassônico (mesma fórmula para TX e para validar RX)."""
    return ULTRASONIC_CHECKSUM_CONST + address + data_msb + data_lsb


def modbus_crc(buffer: bytes) -> int:
    """CRC-16 Modbus (poly 0xA001). Retorna inteiro; no frame vai little-endian (lo, hi)."""
    crc = 0xFFFF
    for byte in buffer:
        crc ^= byte & 0xFF
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF
