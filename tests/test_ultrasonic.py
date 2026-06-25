"""Testes do driver ultrassônico usando o simulador (sem hardware)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.config.models import ConfigSensorDistancia
from cubagempi.drivers.ultrasonic import IndexSensor, UltrasonicSensor
from cubagempi.hal.rs485 import MockRs485
from cubagempi.sim import UltrasonicSimulator


def _sensor(distancias=None, **cfg_kwargs):
    sim = UltrasonicSimulator(distancias=distancias, ruido=0)
    rs485 = MockRs485(sim.responder)
    cfg = ConfigSensorDistancia(**cfg_kwargs)
    return UltrasonicSensor(rs485, cfg), sim


def test_read_raw_ok():
    sensor, _ = _sensor({11: 1074, 12: 0, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0},
                        enderecos=[11, 0, 0, 0], enderecos2=[0, 0, 0, 0])
    assert sensor.read_raw(11) == 1074


def test_read_distance_sem_correcao():
    sensor, _ = _sensor({11: 1000}, enderecos=[11, 0, 0, 0], enderecos2=[0, 0, 0, 0],
                        temperatura=0.0)  # sem correção -> 1000/10 = 100.0 cm
    assert abs(sensor.read_distance_cm(11) - 100.0) < 1e-6


def test_timeout_endereco_inexistente():
    sensor, _ = _sensor(enderecos=[99, 0, 0, 0], enderecos2=[0, 0, 0, 0])
    assert sensor.read_raw(99) == -1  # ERR_TIMEOUT


def test_dual_pega_menor():
    # sensor lógico 0 é duplo (11/12); deve usar o MENOR positivo do par.
    sensor, _ = _sensor({11: 1100, 12: 1000, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0},
                        enderecos=[11, 0, 0, 0], enderecos2=[12, 0, 0, 0],
                        leituras=10, temperatura=0.0, delay_sensores_ms=0)
    medidas = sensor.ler_sensores()
    # 1000/10 = 100 cm (menor do par)
    assert abs(medidas[IndexSensor.DIREITA] - 100.0) < 1e-6


def test_ler_sensores_completo():
    sensor, _ = _sensor(temperatura=0.0, delay_sensores_ms=0)
    medidas = sensor.ler_sensores()
    assert set(medidas.keys()) == set(IndexSensor)
    assert abs(medidas[IndexSensor.DIREITA] - 25.0) < 0.5    # min(255,250)/10
    assert abs(medidas[IndexSensor.ALTURA] - 45.3) < 0.5     # min(463,453)/10


def test_out_of_range():
    sensor, _ = _sensor({11: 2000, 12: 2000, 13: 0, 14: 0, 15: 0, 16: 0, 17: 0, 18: 0},
                        enderecos=[11, 0, 0, 0], enderecos2=[12, 0, 0, 0],
                        maximo_sensor=[124.0, 41.0, 41.0, 66.0], temperatura=0.0,
                        delay_sensores_ms=0)
    medidas = sensor.ler_sensores()
    assert sensor.is_out_of_range(medidas)  # 200 cm > 124


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_ultrasonic")
