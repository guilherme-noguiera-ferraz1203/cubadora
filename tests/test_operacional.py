"""Testes da camada operacional (Onda 1): aferição, etiqueta, nota+volumes, comandos."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.cubagem.calibracao import Calibracao
from cubagempi.cubagem.dimensions import Cubagem
from cubagempi.cubagem.etiqueta import parse_danfe, parse_etiqueta
from cubagempi.config.models import ConfigEtiqueta, ConfigCalibracao


def _app(**kw):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 6
    cfg.modo_teste = True            # libera a aferição p/ testar cubagem direto
    for k, v in kw.items():
        setattr(cfg, k, v)
    return App(cfg, simulado=True, db_path=":memory:")


def test_calibracao_verifica_objeto_padrao():
    cal = Calibracao(ConfigCalibracao(altura=78, largura=37, comprimento=31, peso=2.17,
                                      range_peso=0.3, range_sensor=2.0), modo_teste=False)
    cub = Cubagem(altura=78.3, largura=37.2, comprimento=31.4, peso=2.17)
    assert cal.calibrar(cub) is True
    assert cal.is_calibrado()


def test_fluxo_cubagem_com_modo_teste():
    app = _app()
    r = app.tratar_etiqueta("CAIXA1")
    assert r["tipo"] == "cubagem"
    assert app.contador.todos().get("cubagem") == 1
    app.stop()


def test_comandos_principais():
    app = _app()
    assert "IP:" in app.tratar_etiqueta("*ip*")["mensagem"]
    assert "envelope" in app.tratar_etiqueta("*e*")["mensagem"].lower()
    assert "DANFE" in app.tratar_etiqueta("*danfe*")["mensagem"]
    assert "spec" not in app.tratar_etiqueta("*spec*")["mensagem"].lower()  # retorna a versão
    assert app.tratar_etiqueta("*total*")["tipo"] == "comando"
    app.stop()


def test_modo_envelope():
    app = _app()
    app.tratar_etiqueta("*e*")               # liga envelope
    r = app.tratar_etiqueta("ENV1")
    c = r["cubagem"]
    assert c["altura"] == 1.0 and c["largura"] == 1.0 and c["comprimento"] == 1.0
    assert c["peso"] > 0
    app.stop()


def test_nota_mais_volumes():
    app = _app()
    app.config.etiqueta.nota_mais_volumes = True
    r1 = app.tratar_etiqueta("NF50+2")       # registra a nota
    assert r1["tipo"] == "info"
    r2 = app.tratar_etiqueta("")             # volume 1
    assert r2["tipo"] == "cubagem"
    app.stop()


def test_parse_etiqueta_posicional():
    cfg = ConfigEtiqueta(posicao_nota=0, tamanho_nota=6, posicao_cnpj=6, tamanho_cnpj=14)
    info = parse_etiqueta("000123" + "12345678000199", cfg)
    assert info.nota == "000123"
    assert info.cnpj == "12345678000199"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_operacional")
