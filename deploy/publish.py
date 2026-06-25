#!/usr/bin/env python3
"""Publica uma nova versão do software para a frota.

Faz: (1) ajusta a versão em cubagempi/__init__.py, (2) empacota o código (sem config/dados),
(3) envia ao servidor de frota. A partir daí, todos os equipamentos baixam e atualizam sozinhos.

Uso:
    python deploy/publish.py --servidor http://SEU_SERVIDOR:9000 --versao 1.1.0
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import urllib.request
import zipfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Pastas/arquivos que ENTRAM no pacote (apenas código).
INCLUI = ["cubagempi", "scripts", "deploy", "fleet", "requirements.txt", "requirements-pi.txt",
          "config.example.yaml"]
# Nunca empacotar (config e dados locais do equipamento).
EXCLUI = {"config.yaml", "cubagem.db", "data", "bkp", "_docbuild", "__pycache__", "fleet.db", "packages"}


def set_versao(versao: str) -> None:
    init = os.path.join(RAIZ, "cubagempi", "__init__.py")
    with open(init, "r", encoding="utf-8") as f:
        txt = f.read()
    txt = re.sub(r'__version__\s*=\s*"[^"]*"', f'__version__ = "{versao}"', txt)
    with open(init, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"Versão ajustada para {versao} em cubagempi/__init__.py")


def empacotar() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base in INCLUI:
            caminho = os.path.join(RAIZ, base)
            if os.path.isfile(caminho):
                z.write(caminho, base)
            elif os.path.isdir(caminho):
                for root, dirs, files in os.walk(caminho):
                    dirs[:] = [d for d in dirs if d not in EXCLUI]
                    for fn in files:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, RAIZ)
                        if any(part in EXCLUI for part in rel.split(os.sep)):
                            continue
                        z.write(full, rel.replace(os.sep, "/"))
    return buf.getvalue()


def publicar(servidor: str, versao: str, dados: bytes, user: str = "", senha: str = "") -> None:
    url = servidor.rstrip("/") + f"/api/publish?versao={versao}"
    headers = {"Content-Type": "application/zip"}
    if user:
        import base64
        token = base64.b64encode(f"{user}:{senha}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=dados, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        print(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica uma versão para a frota")
    ap.add_argument("--servidor", required=True, help="URL do servidor de frota (ex.: http://host:9000)")
    ap.add_argument("--versao", required=True, help="número da nova versão (ex.: 1.1.0)")
    ap.add_argument("--so-empacotar", action="store_true", help="só gera o zip local, não envia")
    ap.add_argument("--user", default="", help="usuário (se o painel estiver protegido por senha)")
    ap.add_argument("--senha", default="", help="senha (se o painel estiver protegido por senha)")
    args = ap.parse_args()

    set_versao(args.versao)
    dados = empacotar()
    print(f"Pacote: {len(dados)} bytes")
    if args.so_empacotar:
        out = os.path.join(RAIZ, f"cubagem-{args.versao}.zip")
        with open(out, "wb") as f:
            f.write(dados)
        print("Salvo em", out)
        return 0
    publicar(args.servidor, args.versao, dados, args.user, args.senha)
    print("Pronto! Os equipamentos vão atualizar para", args.versao, "no próximo heartbeat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
