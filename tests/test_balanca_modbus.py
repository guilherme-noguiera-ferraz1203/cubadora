"""Testes da Fase 4: balança via ATmega/I²C, Modbus RTU e CLP (com simuladores)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.config.models import ConfigBalanca
from cubagempi.drivers.atmega_i2c import AtmegaI2C
from cubagempi.drivers.balanca import Balanca485, BalancaAtmegaI2C
from cubagempi.drivers.clp import Clp485
from cubagempi.drivers.modbus import Modbus485, build_frame, is_crc_ok, rx_length
from cubagempi.hal.i2c import MockI2C
from cubagempi.hal.rs485 import MockRs485
from cubagempi.sim import AtmegaSimulator, ModbusSimulator


def test_balanca_atmega_i2c():
    sim = AtmegaSimulator(peso=2.17, casa_decimal_peso=100.0, versao=3.4, estabilizado=True)
    i2c = MockI2C(sim.handler)
    atmega = AtmegaI2C(i2c, address=4, watchdog=False)
    assert abs(atmega.get_version() - 3.4) < 1e-6
    balanca = BalancaAtmegaI2C(atmega, ConfigBalanca())
    assert abs(balanca.get_media_peso() - 2.17) < 1e-6


def test_balanca_atmega_negativo():
    sim = AtmegaSimulator(peso=-1.5, casa_decimal_peso=100.0)
    atmega = AtmegaI2C(MockI2C(sim.handler), watchdog=False)
    balanca = BalancaAtmegaI2C(atmega, ConfigBalanca())
    assert abs(balanca.get_media_peso() - (-1.5)) < 1e-6


def test_modbus_frame_e_crc():
    frame = build_frame(2, 3, 400, 1)
    assert is_crc_ok(frame)
    assert rx_length(frame) == 1 * 2 + 5


def test_balanca_modbus():
    sim = ModbusSimulator()
    sim.set(2, 400, 1234)  # peso bruto
    rs485 = MockRs485(sim.responder)
    modbus = Modbus485(rs485)
    cfg = ConfigBalanca(casa_decimal_peso=100.0, peso_minimo=0.2, ajuste_peso=0.0)
    balanca = Balanca485(modbus, cfg)
    assert abs(balanca.read_peso() - 12.34) < 1e-6


def test_clp_read_write():
    sim = ModbusSimulator()
    rs485 = MockRs485(sim.responder)
    clp = Clp485(Modbus485(rs485), enabled=True)
    clp.write_nova_etiqueta(3)
    assert sim.get(1, 240) == 3
    sim.set(1, 1010, 1)  # nova pesagem disponível
    assert clp.is_peso_disponivel()
    clp.zerar_nova_pesagem()
    assert not clp.is_peso_disponivel()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_balanca_modbus")
