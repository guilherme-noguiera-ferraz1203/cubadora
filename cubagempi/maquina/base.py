"""Base das máquinas: status, observadores e interface comum."""

from __future__ import annotations

import enum
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from ..cubagem import Cubagem

log = logging.getLogger(__name__)


class Cor(enum.Enum):
    VERDE = "verde"
    AMARELO = "amarelo"
    VERMELHO = "vermelho"


@dataclass
class Status:
    cor: Cor = Cor.AMARELO
    texto: str = "Aferição"


CubagemListener = Callable[[Cubagem], None]
StatusListener = Callable[[Status], None]


class Maquina(ABC):
    """Interface comum das máquinas. Produz Cubagem e notifica observadores."""

    def __init__(self) -> None:
        self._cub_listeners: list[CubagemListener] = []
        self._status_listeners: list[StatusListener] = []
        self.status = Status()
        self._stop = threading.Event()
        self.running = False

    # ----- observadores
    def add_cubagem_listener(self, cb: CubagemListener) -> None:
        self._cub_listeners.append(cb)

    def add_status_listener(self, cb: StatusListener) -> None:
        self._status_listeners.append(cb)

    def _notify_cubagem(self, cub: Cubagem) -> None:
        for cb in self._cub_listeners:
            try:
                cb(cub)
            except Exception:  # noqa: BLE001
                log.exception("Erro em listener de cubagem")

    def set_status(self, cor: Cor, texto: str) -> None:
        self.status = Status(cor, texto)
        for cb in self._status_listeners:
            try:
                cb(self.status)
            except Exception:  # noqa: BLE001
                log.exception("Erro em listener de status")

    # ----- ciclo de vida
    @abstractmethod
    def ler_cubagem(self, etiqueta: str = "") -> Cubagem:
        """Executa uma medição completa e retorna a cubagem."""

    def run(self) -> None:
        """Loop de fundo da máquina (heartbeat, esteira, etc.). Default: nada."""
        self.running = True

    def stop(self) -> None:
        self._stop.set()
        self.running = False
