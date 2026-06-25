"""Agente de frota: reporta ao painel central (heartbeat) e aplica a versão-alvo.

A cada `heartbeat_segundos`, o equipamento envia ao servidor: identidade, unidade, versão,
status, produção e os eventos/erros novos. O servidor responde com a versão-alvo; se houver
versão nova e `auto_update` estiver ligado, o equipamento baixa, aplica e reinicia sozinho.

Pull-based: só o servidor precisa de endereço fixo; os equipamentos podem estar em redes/unidades
diferentes, atrás de NAT.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

from .. import __version__ as SW_VERSION
from ..core.log_buffer import get_log_buffer

log = logging.getLogger(__name__)


class FleetAgent:
    def __init__(self, app):
        self.app = app
        self.cfg = app.config.frota
        self._stop = threading.Event()
        self._ultimo_seq = 0

    def start(self) -> None:
        if not self.cfg.servidor:
            log.info("Frota: sem servidor configurado; agente desativado.")
            return
        threading.Thread(target=self._loop, name="fleet-agent", daemon=True).start()
        log.info("Frota: agente ativo (servidor=%s, intervalo=%ds)", self.cfg.servidor, self.cfg.heartbeat_segundos)

    def stop(self) -> None:
        self._stop.set()

    def _coletar_eventos(self) -> list[dict]:
        self._ultimo_seq, eventos = get_log_buffer().desde(self._ultimo_seq, ("WARNING", "ERROR", "CRITICAL"))
        return eventos[-30:]  # no máximo 30 por heartbeat

    def _payload(self) -> dict:
        ident = self.app.identidade()
        return {
            "device_id": ident["device_id"],
            "nome": ident["nome"],
            "unidade": self.cfg.unidade,
            "versao": SW_VERSION,
            "modelo": ident["modelo"],
            "ip": ident["ip"],
            "status": self.app.maquina.status.texto,
            "status_cor": self.app.maquina.status.cor.value,
            "aferido": self.app.calibracao.is_calibrado(),
            "integracao": self.app.nome_integracao(),
            "producao": self.app.producao_dict(),
            "eventos": self._coletar_eventos(),
        }

    def heartbeat(self) -> dict | None:
        url = self.cfg.servidor.rstrip("/") + "/api/heartbeat"
        body = json.dumps(self._payload()).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except Exception as exc:  # noqa: BLE001
            log.debug("Frota: heartbeat falhou (%s)", exc)
            return None

    def _verificar_update(self, resposta: dict) -> None:
        alvo = (resposta or {}).get("versao_alvo")
        if alvo and alvo != SW_VERSION and self.cfg.auto_update:
            log.warning("Frota: versão-alvo %s difere da atual %s; atualizando...", alvo, SW_VERSION)
            self.app.atualizacao.aplicar_versao(self.cfg.servidor, alvo)  # baixa, aplica e reinicia

    def _loop(self) -> None:
        # primeiro heartbeat logo após subir, depois no intervalo
        time.sleep(5)
        while not self._stop.is_set():
            resp = self.heartbeat()
            if resp is not None:
                self._verificar_update(resp)
            self._stop.wait(max(30, self.cfg.heartbeat_segundos))
