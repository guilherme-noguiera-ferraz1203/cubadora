"""Testes: estatísticas de produção, logo, integração editável e identidade (adoção)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina


def _app(config_path=None, integracao=None):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    if integracao is not None:
        cfg.integracao = integracao
    return App(cfg, simulado=True, db_path=":memory:", config_path=config_path)


def test_producao_conta_volumes():
    app = _app()
    app.tratar_etiqueta("CX1")
    app.tratar_etiqueta("CX2")
    p = app.producao_dict()
    assert p["volumes"] == 2
    assert p["vol_h"] >= 2
    app.stop()


def test_identidade_e_adocao():
    path = os.path.join(tempfile.gettempdir(), "cub_frota.yaml")
    app = _app(config_path=path)
    ident = app.identidade()
    assert ident["device_id"].startswith("cub-")
    assert ident["adotado"] is False
    app.adotar("https://frota.exemplo.com", "chave123")
    assert app.identidade()["adotado"] is True
    assert app.config.frota.servidor == "https://frota.exemplo.com"
    if os.path.exists(path):
        os.remove(path)
    app.stop()


def test_integracao_editavel():
    app = _app(integracao=[{"name": "A", "enabled": "true"}])
    assert app.nome_integracao() == "A"
    app.salvar_integracao_config([{"name": "MEU_ERP", "enabled": "true", "$target": "https://x"}])
    assert app.nome_integracao() == "MEU_ERP"
    assert app.get_integracao_config()[0]["$target"] == "https://x"
    app.stop()


def test_logo_save_read():
    app = _app()
    app.config.logo_path = os.path.join(tempfile.gettempdir(), "cub_logo_test.png")
    assert app.tem_logo() is False
    app.salvar_logo(b"\x89PNG\r\n\x1a\n teste")
    assert app.tem_logo() is True
    assert app.ler_logo().startswith(b"\x89PNG")
    os.remove(app.config.logo_path)
    app.stop()


def test_status_tem_producao():
    app = _app()
    s = app.status_dict()
    assert "producao" in s and "nome_equipamento" in s and "tem_logo" in s
    app.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_ui_producao")
