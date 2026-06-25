"""Configuração de logging (console + arquivo rotativo opcional)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .log_buffer import get_log_buffer

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO, logfile: str | None = None) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Evita handlers duplicados em chamadas repetidas (ex.: testes).
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_FORMAT, _DATEFMT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Buffer em memória para a tela/web (/api/log)
    root.addHandler(get_log_buffer())

    if logfile:
        file_handler = RotatingFileHandler(
            logfile, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
