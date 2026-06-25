#!/usr/bin/env python3
"""Inicia o servidor de frota (painel central).

Uso:  python fleet/run.py [--porta 9000] [--db fleet.db]
Depois abra http://<ip-do-servidor>:9000 no navegador.
Nos equipamentos, configure  frota.servidor: http://<ip-do-servidor>:9000
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fleet.server import FleetServer


def main() -> int:
    ap = argparse.ArgumentParser(description="Servidor de frota da cubagem")
    ap.add_argument("--porta", type=int, default=9000)
    ap.add_argument("--db", default="fleet.db")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    FleetServer(args.porta, args.db).start(background=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
