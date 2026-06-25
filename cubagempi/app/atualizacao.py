"""Atualização de software OTA (porta de AtualizacaoRestClient + check-restore).

Baixa o pacote da versão-alvo do servidor de frota, faz backup do código atual, extrai por cima
(preservando config.yaml, cubagem.db e data/) e reinicia a aplicação.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import urllib.request
import zipfile

log = logging.getLogger(__name__)

# Itens que NÃO devem ser sobrescritos/incluídos no pacote (config e dados locais).
PRESERVAR = {"config.yaml", "cubagem.db", "data", "bkp", "_docbuild", "__pycache__"}


def _app_root() -> str:
    # .../python/cubagempi/app/atualizacao.py -> .../python
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Atualizacao:
    def __init__(self, servidor: str = "", versao_atual: str = "", base_dir: str | None = None):
        self.servidor = (servidor or "").rstrip("/")
        self.versao_atual = versao_atual
        self.base_dir = base_dir or _app_root()

    def _backup(self, versao_atual: str) -> str:
        destino = os.path.join(self.base_dir, "bkp", versao_atual or "anterior")
        os.makedirs(destino, exist_ok=True)
        # guarda só o código (cubagempi/, scripts/, deploy/)
        for item in ("cubagempi", "scripts", "deploy"):
            origem = os.path.join(self.base_dir, item)
            if os.path.isdir(origem):
                shutil.copytree(origem, os.path.join(destino, item), dirs_exist_ok=True)
        log.info("Backup da versão atual em %s", destino)
        return destino

    def aplicar_versao(self, servidor: str, versao: str) -> str:
        """Baixa o pacote da `versao` no `servidor` e aplica (com backup), depois reinicia."""
        servidor = (servidor or self.servidor).rstrip("/")
        if not servidor:
            return "Servidor de frota não configurado"
        url = f"{servidor}/api/package/{versao}"
        zip_path = os.path.join(self.base_dir, "_update.zip")
        try:
            log.warning("Baixando atualização %s de %s", versao, url)
            urllib.request.urlretrieve(url, zip_path)
            self._backup(self.versao_atual)
            with zipfile.ZipFile(zip_path) as z:
                # segurança: não extrai itens preservados
                for nome in z.namelist():
                    topo = nome.split("/", 1)[0]
                    if topo in PRESERVAR:
                        continue
                    z.extract(nome, self.base_dir)
            os.remove(zip_path)
            log.warning("Atualizado para a versão %s. Reiniciando...", versao)
            self.reiniciar()
            return f"Atualizado para {versao}"
        except Exception as exc:  # noqa: BLE001
            log.exception("Falha ao aplicar a atualização")
            return f"Erro na atualização: {exc}"

    def reiniciar(self) -> None:
        """Reinicia a aplicação carregando o novo código."""
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:  # noqa: BLE001
            if sys.platform.startswith("linux"):
                import subprocess
                subprocess.Popen(["sudo", "systemctl", "restart", "cubagempi"])
