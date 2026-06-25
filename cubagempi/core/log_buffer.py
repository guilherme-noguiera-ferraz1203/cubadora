"""Buffer de log em memória (porta do HtmlHandler do Java) com numeração de sequência.

Mantém as últimas N linhas para a tela/web (/api/log) e permite buscar só as linhas novas
desde um ponto (usado pelo agente de frota para enviar apenas os eventos recentes).
"""

from __future__ import annotations

import logging
from collections import deque

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%H:%M:%S"


class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 500):
        super().__init__()
        self.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
        self.records: deque[tuple[int, str, str]] = deque(maxlen=capacity)  # (seq, nivel, texto)
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._seq += 1
            self.records.append((self._seq, record.levelname, self.format(record)))
        except Exception:  # noqa: BLE001
            pass

    def linhas(self) -> list[str]:
        return [t for _, _, t in self.records]

    def desde(self, seq: int, niveis: tuple[str, ...] | None = None) -> tuple[int, list[dict]]:
        """Retorna (ultimo_seq, eventos) com as linhas de sequência > seq, opcionalmente
        filtradas por nível (ex.: ('WARNING','ERROR'))."""
        eventos = []
        ultimo = seq
        for s, nivel, texto in self.records:
            if s <= seq:
                continue
            ultimo = max(ultimo, s)
            if niveis and nivel not in niveis:
                continue
            eventos.append({"nivel": nivel, "mensagem": texto})
        return ultimo, eventos


_INSTANCE: MemoryLogHandler | None = None


def get_log_buffer() -> MemoryLogHandler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = MemoryLogHandler()
    return _INSTANCE
