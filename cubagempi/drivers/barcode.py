"""Leitor de código de barras / etiqueta (porta de Sick/VMS/EtiquetaSerialListener).

Modelos suportados (config.leitor.modelo):
- SERIAL : scanner serial / USB-CDC (linhas terminadas em CR/LF) via pyserial
- USB    : APELIDO de SERIAL — abre `com_port` com pyserial, igual ao SERIAL.
           ATENÇÃO: NÃO lê teclado/HID. Um scanner "keyboard-wedge" (o tipo mais
           comum, que digita como teclado e aparece em /dev/input/eventX) NÃO
           funciona aqui: ele nem tem /dev/ttyUSB*. Para usá-lo, troque o scanner
           para modo USB-COM/CDC — quase todo modelo tem um código de barras de
           configuração no manual para isso — e aí ele vira /dev/ttyACM0.
- I2C    : leitor atrás do ATmega (lê o device serial via I²C). É o caminho de
           projeto nas máquinas com shield (device 21).
- VMS    : variante serial (mesmo mecanismo do SERIAL)
- NENHUM : desabilitado — É O DEFAULT, e o instalador não mexe nesta seção.
           Instalação nova sai com o leitor DESLIGADO até alguém configurar.

Cada leitor roda numa thread e chama `callback(codigo)` a cada leitura.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from ..config.models import ConfigLeitor

log = logging.getLogger(__name__)

Callback = Callable[[str], None]


class LeitorEtiqueta(ABC):
    def __init__(self, callback: Callback):
        self.callback = callback
        self._stop = threading.Event()

    @abstractmethod
    def _loop(self) -> None: ...

    def start(self) -> None:
        threading.Thread(target=self._loop, name="leitor", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


class MockBarcode(LeitorEtiqueta):
    """Leitor simulado: injeta códigos via feed() (para testes/demo)."""

    def __init__(self, callback: Callback):
        super().__init__(callback)
        self._fila: list[str] = []

    def feed(self, codigo: str) -> None:
        self.callback(codigo)

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._fila:
                self.callback(self._fila.pop(0))
            time.sleep(0.05)


class SerialBarcode(LeitorEtiqueta):
    def __init__(self, callback: Callback, com_port: str, baudrate: int):
        super().__init__(callback)
        import serial  # import tardio

        from ..hal import serial_ports

        # Fixação: aceita nó cru, caminho estável (by-id/by-path) ou fragmento ("CH340").
        # Sem isto o leitor abriria /dev/ttyUSB0 às cegas — que pode ser o adaptador
        # RS-485 dos sensores, já que os dois têm o mesmo default de porta.
        porta = com_port
        if serial_ports.e_identidade_usb(com_port):
            porta, info = serial_ports.resolver_porta(com_port)
            serial_ports.aviso_se_instavel("Leitor", com_port, info)
            if info is not None:
                log.info("Leitor fixado: %s -> %s (%s)", com_port, porta, info.descricao())
        self._ser = serial.Serial(porta, baudrate, timeout=0.5)

    def _loop(self) -> None:
        buf = bytearray()
        while not self._stop.is_set():
            try:
                data = self._ser.read(64)
                if data:
                    buf.extend(data)
                    while b"\n" in buf or b"\r" in buf:
                        sep = min((buf.index(c) for c in (b"\n", b"\r") if c in buf), default=-1)
                        linha = bytes(buf[:sep]).decode("ascii", "ignore").strip()
                        del buf[:sep + 1]
                        if linha:
                            self.callback(linha)
            except Exception:  # noqa: BLE001
                log.exception("Erro no leitor serial")
                time.sleep(0.5)


class I2cBarcode(LeitorEtiqueta):
    """Leitor atrás do ATmega: faz polling do device serial via I²C."""

    def __init__(self, callback: Callback, atmega, device: int):
        super().__init__(callback)
        self.atmega = atmega
        self.device = device

    def _loop(self) -> None:
        from .scale_protocol import DelimitedBuffer

        delim = DelimitedBuffer((2, 32, 48), 13, True)  # STX/printáveis até CR (ajustável)
        while not self._stop.is_set():
            try:
                novo = self.atmega.read_device_serial(self.device)
                pacote = delim.process(novo)
                if pacote:
                    codigo = "".join(chr(b) for b in pacote if 32 <= b < 127).strip()
                    if codigo:
                        self.callback(codigo)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)


def create_leitor(config: ConfigLeitor, callback: Callback, atmega=None,
                  simulado: bool = False) -> Optional[LeitorEtiqueta]:
    modelo = (config.modelo or "NENHUM").upper()
    if simulado or modelo == "NENHUM":
        return MockBarcode(callback) if simulado else None
    try:
        if modelo in ("SERIAL", "VMS", "USB"):
            return SerialBarcode(callback, config.com_port, config.baudrate)
        if modelo == "I2C" and atmega is not None:
            return I2cBarcode(callback, atmega, config.i2c_serial_device)
    except Exception as exc:  # noqa: BLE001
        log.warning("Leitor indisponível (%s)", exc)
    return None
