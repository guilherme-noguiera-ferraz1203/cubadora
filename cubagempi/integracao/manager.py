"""Gerenciador de integrações: executa, enfileira em caso de falha e reprocessa (retry).

Espelha o IntegracaoCommon do Java: para cada integração habilitada, envia a cubagem;
falhas vão para a fila no banco e são reenviadas por um timer.
"""

from __future__ import annotations

import json as jsonlib
import logging
import threading
import time

from ..config.models import AppConfig
from ..cubagem import Cubagem
from ..persistence import Database
from .rest_client import IntegracaoError, RestClient

log = logging.getLogger(__name__)


class IntegracaoManager:
    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self.client = RestClient()
        self.habilitada = True            # alternável pelo comando *i*
        self._stop = threading.Event()

    def integracoes_ativas(self) -> list[dict]:
        return [i for i in self.config.integracao if str(i.get("enabled", "false")).lower() == "true"]

    def executar(self, etiqueta: str, cub: Cubagem, tipo: str = "auto") -> str:
        """Envia a cubagem às integrações ativas. Retorna o status:
        'desligada' | 'sem_integracao' | 'enviado' | 'fila'."""
        if not self.habilitada:
            return "desligada"
        ativas = self.integracoes_ativas()
        if not ativas:
            return "sem_integracao"
        casa = self.config.casa_decimal_medidas
        falhou = False
        for item in ativas:
            try:
                self.client.execute(etiqueta, cub, item, casa)
            except Exception as exc:  # noqa: BLE001 - falhou: enfileira p/ retry
                falhou = True
                log.warning("Integração '%s' falhou (%s); enfileirando", item.get("name", "?"), exc)
                url, body, headers = self.client.render(etiqueta, cub, item, casa)
                wrapper = jsonlib.dumps({
                    "url": url, "body": body, "headers": headers,
                    "timeout": int(item.get("timeout", 5000)),
                    "success_tag": item.get("success-tag", "*"),
                })
                self.db.enfileirar_integracao(etiqueta, wrapper, url)
        return "fila" if falhou else "enviado"

    def processar_fila(self) -> None:
        for pend in self.db.integracoes_pendentes():
            try:
                w = jsonlib.loads(pend["payload"])
                self.client.post(w["url"], w["body"], w["headers"], w["timeout"], w["success_tag"])
                self.db.marcar_integracao(pend["id"], "enviado")
            except Exception as exc:  # noqa: BLE001
                log.debug("Retry da integração %s falhou: %s", pend["id"], exc)
                self.db.marcar_integracao(pend["id"], "pendente")

    def start_retry_timer(self, intervalo_s: int = 10) -> None:
        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.processar_fila()
                except Exception:  # noqa: BLE001
                    log.exception("Erro no timer de integração")
                time.sleep(intervalo_s)
        threading.Thread(target=loop, name="integracao-retry", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
