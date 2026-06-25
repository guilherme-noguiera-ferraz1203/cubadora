"""Testes da Onda 2: leitor de código de barras, LCD e workers (com simuladores)."""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.cubagem.dimensions import Cubagem
from cubagempi.drivers.lcd import MockLcd, LcdView
from cubagempi.drivers.barcode import MockBarcode


def _app():
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    return App(cfg, simulado=True, db_path=":memory:")


def test_lcd_mock_escreve_linhas():
    lcd = MockLcd(); lcd.init()
    view = LcdView(lcd)
    view.on_cubagem(Cubagem(altura=78, largura=37, comprimento=31, peso=2.17))
    assert "A78" in lcd.linhas[0]
    assert "P2.17" in lcd.linhas[1]


def test_leitor_simulado_dispara_medicao():
    app = _app()
    # no modo simulado, o leitor é um MockBarcode
    assert isinstance(app.leitor, MockBarcode)
    app.leitor.feed("CAIXA-SCAN")            # simula uma leitura
    assert app.ultima_cubagem is not None
    assert app.db.ultima_cubagem()["etiqueta"] == "CAIXA-SCAN"
    app.stop()


def test_app_start_stop_com_workers():
    app = _app()
    app.start()                              # sobe leitor + workers + lcd
    time.sleep(0.2)
    app.leitor.feed("CX1")
    assert app.ultima_cubagem is not None
    app.stop()                               # encerra tudo sem erro


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_perifericos")
