"""Contadores e tempos de operação (porta de ContadorService.java).

Persistido no SQLite. Conta: ligado, desligado, cubagens, erros, e segundos ligado/operação.
"""

from __future__ import annotations

import threading
import time

from ..persistence import Database

COUNT_LIGADO = "ligado"
COUNT_DESLIGADO = "desligado"
COUNT_CUBAGEM = "cubagem"
COUNT_ERRO_CUBAGEM = "erro_cubagem"
SEGUNDOS_LIGADO = "segundos_ligado"
SEGUNDOS_OPERACAO = "segundos_operacao"


class ContadorService:
    def __init__(self, db: Database):
        self.db = db
        self._millis_start_operacao = 0.0
        self._stop = threading.Event()
        self.db.inc_contador(COUNT_LIGADO, 1)
        self._start_segundos_ligado()

    def inc_cubagem(self) -> None:
        self.db.inc_contador(COUNT_CUBAGEM, 1)

    def inc_erro_cubagem(self) -> None:
        self.db.inc_contador(COUNT_ERRO_CUBAGEM, 1)

    def inc_desligado(self) -> None:
        self.db.inc_contador(COUNT_DESLIGADO, 1)

    def update_millis_start_operacao(self) -> None:
        self._millis_start_operacao = time.monotonic()

    def inc_segundos_operacao(self) -> None:
        if self._millis_start_operacao:
            seg = int(time.monotonic() - self._millis_start_operacao)
            if seg > 0:
                self.db.inc_contador(SEGUNDOS_OPERACAO, seg)
            self._millis_start_operacao = 0.0

    def _start_segundos_ligado(self) -> None:
        def loop() -> None:
            while not self._stop.wait(60):
                self.db.inc_contador(SEGUNDOS_LIGADO, 60)
        threading.Thread(target=loop, name="contador-ligado", daemon=True).start()

    def todos(self) -> dict[str, int]:
        return self.db.todos_contadores()

    def stop(self) -> None:
        self._stop.set()
