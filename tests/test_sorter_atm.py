"""Testes da Onda 3: Sorter (classificador) e ATM (cabine com estados)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ConfigSorter, ModeloMaquina
from cubagempi.drivers.modbus import Modbus485
from cubagempi.hal.rs485 import MockRs485
from cubagempi.maquina.atm import AtmState, MaquinaAtm
from cubagempi.maquina.sorter import Sorter
from cubagempi.sim import ModbusSimulator


def test_sorter_envia_e_conta():
    sim = ModbusSimulator()
    sorter = Sorter(Modbus485(MockRs485(sim.responder)), ConfigSorter(enabled=True, endereco_clp=1, registro_destino=260))
    sorter.enviar("ET1", 3)
    sorter.enviar("ET2", 3)
    sorter.enviar("ET3", 5)
    assert sim.get(1, 260) == 5            # último destino escrito
    assert sorter.contagem.por_destino[3] == 2
    assert sorter.contagem.total() == 3


def test_sorter_raw():
    sim = ModbusSimulator()
    sorter = Sorter(Modbus485(MockRs485(sim.responder)), ConfigSorter(enabled=True))
    msg = sorter.enviar_raw("*485 1 270 7")
    assert sim.get(1, 270) == 7
    assert "270" in msg


def test_atm_ciclo_completo():
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ATM
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    app = App(cfg, simulado=True, db_path=":memory:")
    assert isinstance(app.maquina, MaquinaAtm)
    cub = app.maquina.simular_ciclo("ATM1")
    assert cub.altura > 0 and cub.largura > 0 and cub.peso > 0
    assert app.maquina.estado == AtmState.OCIOSO
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_sorter_atm")
