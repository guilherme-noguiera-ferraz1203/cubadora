"""Testes: status de rede/integração na tela e cubo de aferição editável pela interface."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.app import sistema
from cubagempi.config.models import AppConfig, ModeloMaquina


def _app(integracao=None):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    if integracao is not None:
        cfg.integracao = integracao
    return App(cfg, simulado=True, db_path=":memory:")


def test_status_tem_rede_e_integracao():
    app = _app()
    s = app.status_dict()
    assert "rede" in s and "ip" in s["rede"] and "tipo" in s["rede"]
    assert "integracao_nome" in s
    app.stop()


def test_nome_integracao_ativa():
    app = _app(integracao=[{"name": "VESTRA_ESL", "enabled": "true"}])
    assert app.nome_integracao() == "VESTRA_ESL"
    app.tratar_etiqueta("*i*")            # desliga a integração
    assert app.nome_integracao() == "desligada"
    app.stop()


def test_tipo_conexao_retorna_string():
    assert isinstance(sistema.tipo_conexao(), str)


def test_cubo_editavel_pela_interface():
    app = _app()
    # define um anteparo qualquer de medidas conhecidas pela "interface" (atualizar_config)
    app.atualizar_config("calibracao", {"altura": "50", "largura": "40",
                                        "comprimento": "30", "peso": "5.0",
                                        "codigo_cubo": "ANTEPARO-X"})
    assert app.config.calibracao.altura == 50.0
    assert app.config.calibracao.codigo_cubo == "ANTEPARO-X"
    # aferir usa as novas dimensões do anteparo
    msg = app.calibrar_com_cubo()
    assert "50.0x40.0x30.0" in msg
    assert app.calibracao.is_calibrado()
    # e o código novo dispara a calibração
    r = app.tratar_etiqueta("ANTEPARO-X")
    assert r["tipo"] == "calibracao"
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_kiosk_status")
