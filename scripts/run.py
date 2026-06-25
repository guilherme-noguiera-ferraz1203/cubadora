#!/usr/bin/env python3
"""Launcher principal do programa de cubagem.

PC (simulado, com GUI + web):   python scripts/run.py
PC headless (só web):           python scripts/run.py --no-gui
Raspberry Pi (produção):        python scripts/run.py --config config.yaml --real --no-gui
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
