"""Testes da edição de configuração via web (foco balança) + persistência YAML."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config import config_to_dict, load_config, save_config
from cubagempi.config.models import AppConfig, ModeloMaquina


def _app(config_path=None):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    return App(cfg, simulado=True, db_path=":memory:", config_path=config_path)


def test_get_config_dict_tem_balanca():
    app = _app()
    d = app.get_config_dict()
    assert "balanca" in d and "ajustes" in d
    assert "casa_decimal_peso" in d["balanca"]
    app.stop()


def test_atualizar_balanca_em_memoria():
    app = _app()
    app.atualizar_config("balanca", {"ajuste_peso": "0.5", "peso_minimo": "0.3"})
    assert abs(app.config.balanca.ajuste_peso - 0.5) < 1e-9
    assert abs(app.config.balanca.peso_minimo - 0.3) < 1e-9
    app.stop()


def test_atualizar_ajustes_aplica_na_medicao():
    app = _app()
    app.atualizar_config("ajustes", {"aux_altura": "200"})
    assert app.config.ajustes.aux_altura == 200.0
    app.stop()


def test_persistencia_yaml(tmp_path=None):
    path = os.path.join(tempfile.gettempdir(), "cub_cfg_test.yaml")
    app = _app(config_path=path)
    app.atualizar_config("balanca", {"casa_decimal_peso": "1000"})
    # recarrega do disco
    cfg2 = load_config(path)
    assert cfg2.balanca.casa_decimal_peso == 1000.0
    os.remove(path)
    app.stop()


def test_escrever_parametro_simulado():
    app = _app()
    msg = app.escrever_parametro_balanca(5001, 8000)
    assert "5001" in msg
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_config_web")
