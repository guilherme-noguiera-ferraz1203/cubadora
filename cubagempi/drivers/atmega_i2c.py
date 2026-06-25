"""Ponte ATmega328P via I²C (porta de AtmegaI2C.java).

O ATmega (endereço 0x04 no bus 1) atua como periférico do Pi:
- lê a balança serial e entrega via I²C (devices 20/21 com checksum)
- expõe GPIO digital (input/output) e versão
- precisa de WATCHDOG: o Pi escreve o device 255 a cada < 500 ms ou o ATmega reseta

Uso típico (balança): readDeviceSerial(20) -> bytes do stream serial da balança.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from ..hal.i2c import I2CBus

log = logging.getLogger(__name__)

# "Devices" (comandos) do ATmega
DEV_SENSOR_1 = 1
DEV_SENSOR_2 = 2
DEV_SENSOR_3 = 3
DEV_SENSOR_4 = 4
DEV_INPUT_STATE = 10
DEV_OUTPUT_STATE = 11
DEV_OUTPUT_LOW = 12
DEV_OUTPUT_HIGH = 13
DEV_DESLIGAR_LEITOR = 14
DEV_READ_VERSION = 15
DEV_SERIAL_0_CHECKSUM = 20
DEV_SERIAL_1_CHECKSUM = 21
DEV_SERIAL_0_CLEAR = 22
DEV_SERIAL_1_CLEAR = 23
DEV_SERIAL_RETRANSMIT = 30
DEV_SERIAL_0_OLD = 100
DEV_SERIAL_1_OLD = 101
DEV_WATCHDOG = 255

CHECKSUM_CONST = 1234
I2C_BUFFER_LENGTH = 32
HARDWARE_VERSION_HAS_CLEAR_BUFFER = 3.2


class AtmegaI2C:
    def __init__(self, i2c: I2CBus, address: int = 4, watchdog: bool = True):
        self.i2c = i2c
        self.address = address
        self._last_write = 0.0
        self.watchdog_enabled = watchdog
        self._version: Optional[float] = None
        self.checksum_error = 0
        self.read_serial_error = 0
        self._lock = threading.RLock()
        if watchdog:
            self._start_watchdog()

    # ---------------------------------------------------------------- baixo nível
    def write_device(self, device: int) -> None:
        with self._lock:
            self.i2c.write_byte(self.address, device)
            self._last_write = time.monotonic() * 1000

    def read_device_int(self, device: int, length: int) -> int:
        with self._lock:
            self.write_device(device)
            time.sleep(0.005)
            data = self.i2c.read_bytes(self.address, length)
        if length == 4:
            return (data[0] << 24) + (data[1] << 16) + (data[2] << 8) + data[3]
        return data[0] * 256 + data[1]

    def read_device_serial(self, device: int, depth: int = 0) -> Optional[list[int]]:
        if depth > 20:
            log.error("Erro de comunicação I²C (profundidade máxima)")
            return None
        has_checksum = device in (DEV_SERIAL_0_CHECKSUM, DEV_SERIAL_1_CHECKSUM)
        with self._lock:
            self.write_device(device)
            time.sleep(0.005)
            data = list(self.i2c.read_bytes(self.address, I2C_BUFFER_LENGTH))

        data_length = data[0]
        if data_length == 0:
            return None

        packet_length = 31 - (2 if has_checksum else 0)
        buffer_rx: list[int] = []
        checksum_expected = CHECKSUM_CONST + device + data_length
        for i in range(min(data_length, packet_length)):
            buffer_rx.append(data[i + 1])
            checksum_expected += data[i + 1]

        if has_checksum:
            checksum_rx = data[30] * 256 + data[31]
            if checksum_expected != checksum_rx:
                self.checksum_error += 1
                log.warning("Erro de checksum I²C (count=%d device=%d rx=%d exp=%d)",
                            self.checksum_error, device, checksum_rx, checksum_expected)
                return self.read_device_serial(DEV_SERIAL_RETRANSMIT, depth + 1)

        # pacote maior que o buffer -> continua lendo
        if data_length > packet_length:
            cont = self.read_device_serial(device, depth + 1)
            if cont:
                buffer_rx.extend(cont)
        return buffer_rx

    # ---------------------------------------------------------------- utilidades
    def clear_serial_buffer(self, serial_device: int, tentativas: int = 3) -> bool:
        try:
            if self.get_version() >= HARDWARE_VERSION_HAS_CLEAR_BUFFER:
                dev = DEV_SERIAL_0_CLEAR if serial_device in (DEV_SERIAL_0_CHECKSUM, DEV_SERIAL_0_OLD) else DEV_SERIAL_1_CLEAR
                return self.read_device_int(dev, 2) == 1
            self.read_device_serial(serial_device)
            return True
        except Exception:  # noqa: BLE001
            if tentativas > 0:
                time.sleep(0.1)
                return self.clear_serial_buffer(serial_device, tentativas - 1)
            log.exception("Erro ao limpar buffer serial do ATmega")
            return False

    def get_version(self) -> float:
        if self._version is None:
            try:
                v = self.read_device_int(DEV_READ_VERSION, 2)
                self._version = v / 10.0 if 0 < v < 255 else 0.0
            except Exception:  # noqa: BLE001
                self._version = 0.0
        return self._version

    def read_input_state(self) -> int:
        """Estado das entradas digitais (ex.: botão de reboot)."""
        return self.read_device_int(DEV_INPUT_STATE, 2)

    def set_output(self, high: bool) -> None:
        """Liga/desliga a saída digital (ex.: luz de sinalização)."""
        self.write_device(DEV_OUTPUT_HIGH if high else DEV_OUTPUT_LOW)

    # ---------------------------------------------------------------- watchdog
    def _start_watchdog(self) -> None:
        def loop() -> None:
            while True:
                try:
                    time.sleep(0.125)
                    if self.watchdog_enabled and time.monotonic() * 1000 - self._last_write >= 500:
                        self.write_device(DEV_WATCHDOG)
                except Exception:  # noqa: BLE001
                    pass
        t = threading.Thread(target=loop, name="atmega-watchdog", daemon=True)
        t.start()
