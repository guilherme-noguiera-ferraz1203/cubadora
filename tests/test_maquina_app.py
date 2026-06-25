"""Testes do fluxo completo (App + máquinas) em modo simulado."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.cubagem import Cubagem
from cubagempi.integracao.rest_client import RestClient


def _app(modelo):
    cfg = AppConfig()
    cfg.modelo_maquina = modelo
    cfg.sensor.delay_sensores_ms = 0       # acelera os testes
    cfg.sensor.leituras = 6
    return App(cfg, simulado=True, db_path=":memory:")


def test_estatica_mede_e_persiste():
    app = _app(ModeloMaquina.ESTATICA_2)
    cub = app.medir("CAIXA1")
    assert cub.altura > 0 and cub.largura > 0 and cub.comprimento > 0
    assert abs(cub.peso - 2.17) < 0.01           # peso do simulador
    assert app.db.ultima_cubagem() is not None    # persistiu
    assert app.db.ultima_cubagem()["etiqueta"] == "CAIXA1"
    app.stop()


def test_camera_usa_medidas_da_camera():
    app = _app(ModeloMaquina.CAMERA)
    cub = app.medir("CAIXA2")
    assert abs(cub.largura - 37.0) < 0.01        # MockCamera (config)
    assert abs(cub.comprimento - 31.0) < 0.01
    assert cub.altura > 0
    app.stop()


def test_comando_ip():
    app = _app(ModeloMaquina.ESTATICA_2)
    r = app.tratar_etiqueta("*ip*")
    assert r["tipo"] == "comando" and "IP:" in r["mensagem"]
    app.stop()


def test_alternar_integracao():
    app = _app(ModeloMaquina.ESTATICA_2)
    assert app.integracao.habilitada
    app.tratar_etiqueta("*i*")
    assert not app.integracao.habilitada
    app.stop()


def test_rest_client_render():
    cfg_item = {
        "$target": "https://exemplo/api",
        "json": '{"volume":{"code":"$etiqueta","weight":$peso,"length":$comprimento,"width":$largura,"height":$altura}}',
        "medida-fator": "0.01", "medida-format": "%.2f",
        "peso-fator": "1", "peso-format": "%.2f",
        "header-Authorization": "Bearer XYZ",
        "success-tag": "*", "enabled": "true",
    }
    cub = Cubagem(altura=78.4, largura=37.3, comprimento=31.4, peso=2.17, etiqueta="ET1")
    url, body, headers = RestClient().render("ET1", cub, cfg_item, casa_decimal=1)
    assert url == "https://exemplo/api"
    assert headers["Authorization"] == "Bearer XYZ"
    # 78.4 cm * 0.01 = 0.78 m
    assert '"height":0.78' in body
    assert '"code":"ET1"' in body
    assert '"weight":2.17' in body


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_maquina_app")
