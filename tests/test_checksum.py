"""Testes dos checksums (ultrassônico e Modbus CRC)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.drivers.checksum import modbus_crc, ultrasonic_checksum
from cubagempi.drivers.ultrasonic import UltrasonicSensor


def test_ultrasonic_checksum_formula():
    # checksum = 1234 + endereco + dataMsb + dataLsb
    assert ultrasonic_checksum(11, 32, 1) == 1234 + 11 + 32 + 1


def test_build_frame_roundtrip():
    frame = UltrasonicSensor.build_frame(11, 32, 1)
    assert len(frame) == 5
    cs = frame[3] * 256 + frame[4]
    assert cs == ultrasonic_checksum(11, 32, 1)


def test_modbus_crc_known_value():
    # Frame Modbus clássico: 01 03 00 00 00 01 -> CRC 0x0A84 (lo=0x84, hi=0x0A)
    crc = modbus_crc(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01]))
    assert crc & 0xFF == 0x84
    assert (crc >> 8) & 0xFF == 0x0A


if __name__ == "__main__":
    test_ultrasonic_checksum_formula()
    test_build_frame_roundtrip()
    test_modbus_crc_known_value()
    print("OK test_checksum")
