"""Workers de fundo (porta de TemperaturaWorker e RebootWorker do Java).

- HeartbeatWorker : pisca o LED de status (sinal de "vivo")
- TemperaturaWorker: lê a temperatura do sensor ultrassônico e atualiza o config (correção do som)
- RebootWorker    : monitora o botão de reboot (via ATmega) e reinicia o Pi
"""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time

log = logging.getLogger(__name__)


class HeartbeatWorker:
    def __init__(self, led, intervalo: float = 0.5):
        self.led = led
        self.intervalo = intervalo
        self._stop = threading.Event()

    def start(self) -> None:
        def loop() -> None:
            while not self._stop.wait(self.intervalo):
                try:
                    self.led.toggle()
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=loop, name="heartbeat", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


class TemperaturaWorker:
    def __init__(self, sensor, config_sensor, on_temp=None):
        self.sensor = sensor
        self.cfg = config_sensor
        self.on_temp = on_temp
        self._stop = threading.Event()

    def start(self) -> None:
        if not self.cfg.endereco_temperatura:
            return

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    temp = self.sensor.read_temperatura()
                    if temp is not None:
                        self.cfg.temperatura = temp
                        if self.on_temp:
                            self.on_temp(temp)
                        log.info("Temperatura ultrassônico: %.1f °C", temp)
                        self._stop.wait(self.cfg.intervalo_temperatura_s)
                    else:
                        self._stop.wait(5)
                except Exception:  # noqa: BLE001
                    self._stop.wait(5)
        threading.Thread(target=loop, name="temperatura", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


class RebootWorker:
    """Monitora o botão de reboot via ATmega (estado das entradas) e reinicia."""

    def __init__(self, atmega, luz=None):
        self.atmega = atmega
        self.luz = luz
        self._stop = threading.Event()

    def start(self) -> None:
        if self.atmega is None:
            return

        def loop() -> None:
            apertado_desde = None
            while not self._stop.is_set():
                try:
                    estado = self.atmega.read_input_state()
                    if estado & 0x01:  # bit do botão de reboot
                        if apertado_desde is None:
                            apertado_desde = time.monotonic()
                        elif time.monotonic() - apertado_desde > 3:  # segurar 3s
                            self._reboot()
                            return
                    else:
                        apertado_desde = None
                except Exception:  # noqa: BLE001
                    pass
                self._stop.wait(0.2)
        threading.Thread(target=loop, name="reboot-button", daemon=True).start()

    def _reboot(self) -> None:
        log.warning("Botão de reboot acionado")
        if sys.platform.startswith("linux"):
            subprocess.Popen(["sudo", "reboot"])

    def stop(self) -> None:
        self._stop.set()
