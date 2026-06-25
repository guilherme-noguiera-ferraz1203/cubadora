"""Camada RS-485 half-duplex (núcleo da comunicação).

Espelha a lógica do Rs485Pi4j.java do sistema original:
  flush -> DE alto -> escreve -> aguarda (nbytes*10000/baud µs) -> DE baixo -> lê resposta.

O barramento RS-485 (/dev/ttyAMA0) é compartilhado por:
- sensores ultrassônicos (protocolo proprietário de 5 bytes)
- balança Modbus e CLP (modelos dinâmicos)

Implementações:
- PiRs485   : real, pyserial + pino DE (gpiozero)
- MockRs485 : simulada, usa um "responder" callable(tx, length_rx) -> rx
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from ..config.models import ConfigRs485
from .gpio import OutputPin, create_output_pin

log = logging.getLogger(__name__)

# Um responder simula os dispositivos do barramento: recebe o frame TX e o tamanho
# esperado de resposta, devolve os bytes RX (ou None para timeout).
Responder = Callable[[bytes, int], Optional[bytes]]


def resolver_porta_serial(preferida: str) -> str:
    """Escolhe a porta serial existente (lida com diferenças entre Pi 3/4/5 e SO).

    `/dev/serial0` é o symlink estável; cai para ttyAMA0/ttyS0 conforme o modelo.
    """
    candidatos = [preferida, "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0", "/dev/ttyAMA10"]
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return preferida


class Rs485(ABC):
    @abstractmethod
    def open(self, baudrate: int) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, buffer: bytes, length_rx: int) -> Optional[bytes]:
        """Escreve `buffer` e lê até `length_rx` bytes (ou timeout). None = sem resposta."""

    def __enter__(self) -> "Rs485":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class PiRs485(Rs485):
    """Implementação real no Raspberry Pi."""

    def __init__(self, config: ConfigRs485, real_gpio: bool | None = None) -> None:
        import serial  # import tardio: pyserial só é necessário no Pi

        self._serial_mod = serial
        self.config = config
        self.baudrate = config.baudrate
        self.timeout_ms = config.timeout_ms
        self.min_write_interval_ms = config.millis_min_write_interval
        self._last_write_ms = 0.0

        self._de: OutputPin = create_output_pin(config.de_pin_bcm, initial=False, real=real_gpio)
        self._ser = serial.Serial()
        self._ser.port = resolver_porta_serial(config.serial_port)
        if self._ser.port != config.serial_port:
            log.warning("Porta %s não existe; usando %s", config.serial_port, self._ser.port)
        self.open(self.baudrate)

    def open(self, baudrate: int) -> None:
        if self._ser.is_open:
            self._ser.close()
        self._ser.baudrate = baudrate
        self._ser.bytesize = self._serial_mod.EIGHTBITS
        self._ser.parity = self._serial_mod.PARITY_NONE
        self._ser.stopbits = self._serial_mod.STOPBITS_ONE
        self._ser.timeout = 0          # leitura não-bloqueante; controlamos o timeout manualmente
        self._ser.open()
        self.baudrate = baudrate
        log.info("RS-485 aberto em %s @ %d 8N1 (DE=BCM%d)",
                 self.config.serial_port, baudrate, self.config.de_pin_bcm)

    def close(self) -> None:
        try:
            if self._ser.is_open:
                self._ser.close()
        finally:
            self._de.close()

    def _wait_min_interval(self) -> None:
        while abs(time.monotonic() * 1000 - self._last_write_ms) <= self.min_write_interval_ms:
            time.sleep(0.001)

    def write(self, buffer: bytes, length_rx: int) -> Optional[bytes]:
        self._wait_min_interval()
        try:
            self._ser.reset_input_buffer()
            self._de.high()                       # habilita transmissão
            time.sleep(0.001)
            self._ser.write(buffer)
            self._ser.flush()                     # garante envio físico
            # mantém DE alto o tempo de transmitir todos os bytes (10 bits/byte)
            micros = len(buffer) * 10_000.0 / self.baudrate
            time.sleep(micros / 1_000_000.0)
            self._de.low()                        # volta a escutar
            rx = self._wait_rx(length_rx)
            return rx
        except Exception:
            log.exception("Erro na escrita RS-485 (TX=%s)", list(buffer))
            return None
        finally:
            self._last_write_ms = time.monotonic() * 1000

    def _wait_rx(self, length_rx: int) -> Optional[bytes]:
        buf = bytearray()
        start = time.monotonic()
        timeout_s = self.timeout_ms / 1000.0
        while time.monotonic() - start < timeout_s:
            n = self._ser.in_waiting
            if n:
                buf.extend(self._ser.read(n))
            elif (length_rx == -1 and len(buf) > 0) or (length_rx != -1 and len(buf) >= length_rx):
                break
            else:
                time.sleep(0.001)
        if buf:
            return bytes(buf)
        return None


class MockRs485(Rs485):
    """Implementação simulada: delega a um responder. Para PC/testes."""

    def __init__(self, responder: Responder | None = None, baudrate: int = 115200) -> None:
        self._responder = responder or (lambda tx, n: None)
        self.baudrate = baudrate
        self.is_open = True
        self.tx_log: list[bytes] = []

    def set_responder(self, responder: Responder) -> None:
        self._responder = responder

    def open(self, baudrate: int) -> None:
        self.baudrate = baudrate
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, buffer: bytes, length_rx: int) -> Optional[bytes]:
        self.tx_log.append(bytes(buffer))
        rx = self._responder(bytes(buffer), length_rx)
        log.debug("MockRs485 TX=%s -> RX=%s", list(buffer), list(rx) if rx else None)
        return rx


def create_rs485(
    config: ConfigRs485,
    responder: Responder | None = None,
    real: bool | None = None,
) -> Rs485:
    """Factory: escolhe implementação real (Pi) ou mock.

    - responder != None        -> MockRs485 (simulação explícita)
    - real=True                -> PiRs485 (força hardware)
    - real=None (autodetecção) -> tenta PiRs485; cai para MockRs485 no PC
    """
    if responder is not None and real is not True:
        return MockRs485(responder, config.baudrate)
    try:
        return PiRs485(config, real_gpio=real)
    except Exception as exc:  # noqa: BLE001
        if real is True:
            raise
        log.warning("RS-485 real indisponível (%s); usando MockRs485", exc)
        return MockRs485(responder, config.baudrate)
