"""Testes: assistente de calibração dos sensores, diagnóstico e sistema."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.cubagem.calibracao_sensores import CalibracaoAssistente


def _app():
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    return App(cfg, simulado=True, db_path=":memory:")


def test_assistente_calcula_fatores():
    a = CalibracaoAssistente()
    # objeto 1: alto, perto -> distância menor; objeto 2: baixo -> distância maior
    a.capturar({"altura": 46.0, "fundo": 29.0, "comprimento": 50.0},
               {"altura": 78.0, "largura": 37.0, "comprimento": 31.0})
    a.capturar({"altura": 60.0, "fundo": 39.0, "comprimento": 70.0},
               {"altura": 64.0, "largura": 27.0, "comprimento": 11.0})
    aj = a.calcular()
    assert "altura" in aj and "aux_altura" in aj
    # a fórmula calculada deve reproduzir as alturas reais dos pontos
    f, aux = aj["altura"], aj["aux_altura"]
    assert abs((aux - 46.0 / f) - 78.0) < 0.1
    assert abs((aux - 60.0 / f) - 64.0) < 0.1


def test_assistente_precisa_2_pontos():
    a = CalibracaoAssistente()
    a.capturar({"altura": 46, "fundo": 29, "comprimento": 50}, {"altura": 78, "largura": 37, "comprimento": 31})
    assert not a.pode_calcular()
    try:
        a.calcular()
        assert False, "deveria exigir 2 pontos"
    except ValueError:
        pass


def test_app_calibracao_fluxo_completo():
    app = _app()
    app.hw.ultra_sim.ruido = 0
    # objeto 1
    app.hw.ultra_sim.distancias = {11: 250, 12: 250, 13: 290, 14: 290, 15: 250, 16: 250, 17: 460, 18: 460}
    app.calibrar_capturar(78.0, 37.0, 31.0)
    # objeto 2 (distâncias diferentes)
    app.hw.ultra_sim.distancias = {11: 350, 12: 350, 13: 390, 14: 390, 15: 350, 16: 350, 17: 600, 18: 600}
    r = app.calibrar_capturar(64.0, 27.0, 11.0)
    assert r["pode_calcular"]
    ajustes = app.calibrar_calcular()
    assert "altura" in ajustes
    msg = app.calibrar_aplicar(ajustes)
    assert "aplicada" in msg.lower()
    assert app.config.ajustes.aux_altura == ajustes["aux_altura"]
    app.stop()


def test_diagnostico_apto():
    app = _app()
    d = app.diagnostico()
    assert d["sensores_ok"] is True
    assert d["balanca"]["ok"] is True
    assert d["apto_producao"] is True       # modo_teste libera a aferição
    assert len(d["sensores"]) == 8
    app.stop()


def test_sistema_info():
    app = _app()
    info = app.get_sistema_info()
    assert "hostname" in info and "disco_livre_gb" in info
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_calibracao_diag")
