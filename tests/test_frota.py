"""Testa o ciclo completo de frota: heartbeat -> registro -> versão-alvo -> auto-update -> eventos."""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi import __version__ as SW_VERSION
from cubagempi.app import App
from cubagempi.config.models import AppConfig, ModeloMaquina
from cubagempi.core import setup_logging
from fleet.server import FleetServer


def _app(servidor):
    cfg = AppConfig()
    cfg.modelo_maquina = ModeloMaquina.ESTATICA_2
    cfg.sensor.delay_sensores_ms = 0
    cfg.sensor.leituras = 4
    cfg.modo_teste = True
    cfg.nome_equipamento = "Cubadora 1"
    cfg.frota.servidor = servidor
    cfg.frota.unidade = "CD São Paulo"
    cfg.frota.auto_update = True
    return App(cfg, simulado=True, db_path=":memory:")


def test_ciclo_frota_completo():
    setup_logging(logging.INFO)
    srv = FleetServer(porta=0, db_path=":memory:")
    srv.start()
    base = f"http://127.0.0.1:{srv.port}"
    app = _app(base)

    # impede o reinício real durante o teste; só registra a chamada de atualização
    chamadas = []
    app.atualizacao.aplicar_versao = lambda s, v: chamadas.append((s, v)) or "ok"

    # 1) heartbeat registra o equipamento no servidor
    resp = app.fleet.heartbeat()
    assert resp is not None
    devs = srv.db.list_devices()
    assert len(devs) == 1
    d = devs[0]
    assert d["unidade"] == "CD São Paulo"
    assert d["versao"] == SW_VERSION
    assert d["nome"] == "Cubadora 1"

    # 2) sem versão-alvo nova -> não atualiza
    app.fleet._verificar_update(resp)
    assert not chamadas

    # 3) define uma versão-alvo diferente -> próximo heartbeat dispara o auto-update
    srv.db.set_config("versao_alvo", "9.9.9")
    resp2 = app.fleet.heartbeat()
    app.fleet._verificar_update(resp2)
    assert chamadas and chamadas[-1][1] == "9.9.9"

    # 4) eventos/erros chegam ao servidor
    logging.getLogger("teste.leitura").warning("Erro de leitura no sensor 11")
    app.fleet.heartbeat()
    eventos = srv.db.get_events(d["device_id"], 50)
    assert any("Erro de leitura no sensor 11" in e["mensagem"] for e in eventos)

    srv.stop()
    app.stop()


if __name__ == "__main__":
    test_ciclo_frota_completo()
    print("OK test_frota")
