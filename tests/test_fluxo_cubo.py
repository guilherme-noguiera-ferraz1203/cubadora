"""Testa o fluxo REAL de vocês: cubo de aferição (*cal*) -> calibra -> mede -> integra c/ status."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina


def _app(integracao=None, codigo_cubo=""):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    # cubo de aferição com as dimensões que o simulador "mede" (~78x37x31, peso 2.17)
    cfg.calibracao.altura = 78.0
    cfg.calibracao.largura = 37.0
    cfg.calibracao.comprimento = 31.0
    cfg.calibracao.peso = 2.17
    cfg.calibracao.codigo_cubo = codigo_cubo
    if integracao is not None:
        cfg.integracao = integracao
    return App(cfg, simulado=True, db_path=":memory:")


def test_cal_calibra_e_libera():
    app = _app()
    assert not app.calibracao.is_calibrado()           # começa não aferido
    r = app.tratar_etiqueta("*cal*")                    # lê o cubo
    assert r["tipo"] == "comando"
    assert "Aferição OK" in r["mensagem"]
    assert app.calibracao.is_calibrado()                # agora liberado
    app.stop()


def test_codigo_cubo_dispara_calibracao():
    app = _app(codigo_cubo="CUBO-AFERICAO-001")
    r = app.tratar_etiqueta("CUBO-AFERICAO-001")        # lê o código de barras do cubo
    assert r["tipo"] == "calibracao"
    assert app.calibracao.is_calibrado()
    app.stop()


def test_apos_cal_mede_caixa_com_status_integracao():
    # integração desligada -> status 'sem_integracao' (não há item ativo)
    app = _app()
    app.tratar_etiqueta("*cal*")                        # calibra
    r = app.tratar_etiqueta("CAIXA-001")                # mede uma caixa
    assert r["tipo"] == "cubagem"
    assert r["integracao"] in ("sem_integracao", "enviado", "fila")
    # status do volume foi gravado no banco
    assert app.db.ultima_cubagem()["integracao"] == r["integracao"]
    app.stop()


def test_status_integracao_no_painel():
    app = _app()
    app.tratar_etiqueta("*cal*")
    app.tratar_etiqueta("CAIXA-002")
    s = app.status_dict()
    assert s["ultima_integracao"] in ("sem_integracao", "enviado", "fila")
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_fluxo_cubo")
