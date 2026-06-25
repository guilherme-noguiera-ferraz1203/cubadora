"""Testes da Onda 5: log em memória, atualização OTA, nuvem e integração de sistema."""

import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app import sistema
from cubagempi.app.atualizacao import Atualizacao
from cubagempi.config.models import ConfigCloud
from cubagempi.core import setup_logging
from cubagempi.core.log_buffer import get_log_buffer
from cubagempi.integracao import CloudClient


def test_log_buffer_captura():
    setup_logging(logging.INFO)
    logging.getLogger("teste").info("linha de teste 123")
    linhas = get_log_buffer().linhas()
    assert any("linha de teste 123" in l for l in linhas)


def test_atualizacao_sem_servidor():
    # sem servidor configurado, não tenta baixar nada (e não reinicia)
    at = Atualizacao("", "1.0.0")
    assert "não configurado" in at.aplicar_versao("", "1.1.0").lower()


def test_cloud_desabilitada():
    c = CloudClient(ConfigCloud(), serial_maquina="abc", habilitada=False)
    assert c.enviar_cubagem("ET", __import__("cubagempi.cubagem", fromlist=["Cubagem"]).Cubagem()) is False
    assert c.baixar_config() is False


def test_sistema_get_ip():
    ip = sistema.get_ip()
    assert isinstance(ip, str) and len(ip) > 6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("OK test_sistema_ota")
