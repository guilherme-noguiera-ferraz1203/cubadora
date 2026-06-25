"""Testes da Onda 4: análise de imagem (conversão px->cm por altura)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.app import App
from cubagempi.vision import px_to_cm


def test_px_to_cm_depende_da_altura():
    # escala = a*altura + b ; quanto mais alta a caixa, maior a escala (mais perto da câmera)
    a, b = -0.001, 0.18
    cm_baixo = px_to_cm(1000, 10, a, b)    # altura 10 cm
    cm_alto = px_to_cm(1000, 60, a, b)     # altura 60 cm
    assert cm_alto < cm_baixo               # com a negativo, escala diminui com altura
    assert abs(px_to_cm(1000, 0, a, b) - 1000 * b) < 1e-6


def test_camera_maquina_usa_altura():
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.CAMERA
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    app = App(cfg, simulado=True, db_path=":memory:")
    cub = app.medir("CX-CAM")
    # MockCamera devolve as medidas configuradas
    assert abs(cub.largura - cfg.camera.largura_simulada) < 0.01
    assert abs(cub.comprimento - cfg.camera.comprimento_simulado) < 0.01
    assert cub.altura > 0
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_vision")
