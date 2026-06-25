"""Montagem centralizada do hardware (real no Pi ou simulado no PC).

Constrói e conecta: barramento RS-485, I²C, sensor ultrassônico, balança (ATmega ou Modbus),
Modbus/CLP e câmera — escolhendo as implementações reais ou os simuladores.
"""

from __future__ import annotations

import logging

from ..config.models import AppConfig, ModeloMaquina
from ..drivers.atmega_i2c import AtmegaI2C
from ..drivers.balanca import Balanca485, BalancaAtmegaI2C
from ..drivers.camera import create_camera
from ..drivers.clp import Clp485
from ..drivers.modbus import Modbus485
from ..drivers.ultrasonic import UltrasonicSensor
from ..hal.gpio import create_output_pin
from ..hal.i2c import create_i2c
from ..hal.rs485 import MockRs485, create_rs485
from ..sim import AtmegaSimulator, ModbusSimulator, UltrasonicSimulator, combined_responder

log = logging.getLogger(__name__)

ESTATICOS = {ModeloMaquina.ESTATICA_1, ModeloMaquina.ESTATICA_2, ModeloMaquina.ESTATICA_LCD}


class Hardware:
    def __init__(self, config: AppConfig, simulado: bool):
        self.config = config
        self.simulado = simulado
        self._build()

    def _build(self) -> None:
        cfg = self.config
        modelo = cfg.modelo_maquina

        if self.simulado:
            self.ultra_sim = UltrasonicSimulator(ruido=1)
            self.modbus_sim = ModbusSimulator()
            # Semeia o simulador Modbus: peso da balança dinâmica e flags do CLP.
            self.modbus_sim.set(cfg.balanca.endereco, cfg.balanca.registro_peso,
                                int(round(cfg.balanca.peso_simulado * cfg.balanca.casa_decimal_peso)))
            self.modbus_sim.set(1, 1010, 1)  # nova pesagem disponível (CLP)
            self.atmega_sim = AtmegaSimulator(peso=cfg.balanca.peso_simulado,
                                              casa_decimal_peso=cfg.balanca.casa_decimal_peso)
            self.rs485 = MockRs485(combined_responder(self.ultra_sim, self.modbus_sim), cfg.rs485.baudrate)
            self.i2c = create_i2c(cfg.balanca.i2c_bus, handler=self.atmega_sim.handler)
        else:
            self.rs485 = create_rs485(cfg.rs485, real=True)
            self.i2c = create_i2c(cfg.balanca.i2c_bus, real=True)

        self.sensor = UltrasonicSensor(self.rs485, cfg.sensor, cfg.rs485.timeout_ms)
        self.modbus = Modbus485(self.rs485)
        self.clp = Clp485(self.modbus, cfg.dinamica.clp_enabled)
        self.camera = create_camera(cfg.camera, self.simulado)

        if modelo in ESTATICOS:
            self.atmega = AtmegaI2C(self.i2c, cfg.balanca.i2c_address, watchdog=not self.simulado)
            self.balanca = BalancaAtmegaI2C(self.atmega, cfg.balanca)
        else:
            self.atmega = None
            self.balanca = Balanca485(self.modbus, cfg.balanca)

        # LED de status (heartbeat) — BCM 6 (Pi4j GPIO_22) nos modelos estáticos
        self.led = create_output_pin(6, initial=False, real=None if not self.simulado else False)

        log.info("Hardware montado (%s, %s)", modelo.value, "SIMULADO" if self.simulado else "REAL")

    def init(self) -> None:
        """Inicialização dos dispositivos (versões, baudrate, etc.)."""
        try:
            for addr in self.config.sensor.enderecos:
                if addr:
                    v = self.sensor.read_version(addr)
                    log.info("Ultrassônico %d: versão %s", addr, v)
        except Exception:  # noqa: BLE001
            log.exception("Erro ao inicializar sensores")

    def close(self) -> None:
        try:
            self.rs485.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.i2c.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.camera.close()
        except Exception:  # noqa: BLE001
            pass
