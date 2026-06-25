"""Banco do servidor de frota (SQLite): equipamentos, eventos/erros e versão-alvo."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime

_SCHEMA = """
CREATE TABLE IF NOT EXISTS device (
    device_id   TEXT PRIMARY KEY,
    nome        TEXT,
    unidade     TEXT,
    versao      TEXT,
    modelo      TEXT,
    ip          TEXT,
    status      TEXT,
    status_cor  TEXT,
    aferido     INTEGER,
    integracao  TEXT,
    producao    TEXT,
    last_seen   TEXT,
    primeiro_seen TEXT
);
CREATE TABLE IF NOT EXISTS event (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    nivel     TEXT,
    mensagem  TEXT,
    data      TEXT
);
CREATE TABLE IF NOT EXISTS fleet_config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""


class FleetDB:
    def __init__(self, path: str = "fleet.db"):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # --------------------------------------------------------------- devices
    def upsert_device(self, p: dict) -> None:
        agora = datetime.now().isoformat()
        with self._lock:
            existe = self._conn.execute("SELECT device_id FROM device WHERE device_id=?",
                                        (p.get("device_id"),)).fetchone()
            if existe:
                self._conn.execute(
                    "UPDATE device SET nome=?,unidade=?,versao=?,modelo=?,ip=?,status=?,status_cor=?,"
                    "aferido=?,integracao=?,producao=?,last_seen=? WHERE device_id=?",
                    (p.get("nome"), p.get("unidade"), p.get("versao"), p.get("modelo"), p.get("ip"),
                     p.get("status"), p.get("status_cor"), 1 if p.get("aferido") else 0,
                     p.get("integracao"), json.dumps(p.get("producao") or {}), agora, p.get("device_id")))
            else:
                self._conn.execute(
                    "INSERT INTO device (device_id,nome,unidade,versao,modelo,ip,status,status_cor,"
                    "aferido,integracao,producao,last_seen,primeiro_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p.get("device_id"), p.get("nome"), p.get("unidade"), p.get("versao"), p.get("modelo"),
                     p.get("ip"), p.get("status"), p.get("status_cor"), 1 if p.get("aferido") else 0,
                     p.get("integracao"), json.dumps(p.get("producao") or {}), agora, agora))
            self._conn.commit()

    def list_devices(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM device ORDER BY unidade, nome").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["producao"] = json.loads(d.get("producao") or "{}")
            out.append(d)
        return out

    def get_device(self, device_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["producao"] = json.loads(d.get("producao") or "{}")
        return d

    def create_pending_device(self, device_id: str, nome: str, unidade: str) -> bool:
        """Pré-cadastra um equipamento. Ele aparece no painel como 'aguardando instalação'
        (last_seen NULL) até o primeiro heartbeat. Retorna False se o device_id já existir."""
        agora = datetime.now().isoformat()
        with self._lock:
            existe = self._conn.execute("SELECT device_id FROM device WHERE device_id=?",
                                        (device_id,)).fetchone()
            if existe:
                return False
            self._conn.execute(
                "INSERT INTO device (device_id,nome,unidade,primeiro_seen) VALUES (?,?,?,?)",
                (device_id, nome, unidade, agora))
            self._conn.commit()
        return True

    # --------------------------------------------------------------- events
    def add_events(self, device_id: str, eventos: list[dict]) -> None:
        if not eventos:
            return
        agora = datetime.now().isoformat()
        with self._lock:
            for e in eventos:
                self._conn.execute("INSERT INTO event (device_id,nivel,mensagem,data) VALUES (?,?,?,?)",
                                   (device_id, e.get("nivel", ""), e.get("mensagem", ""), agora))
            self._conn.commit()

    def get_events(self, device_id: str, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT nivel,mensagem,data FROM event WHERE device_id=? ORDER BY id DESC LIMIT ?",
                (device_id, limit)).fetchall()
        return [dict(r) for r in rows]

    # --------------------------------------------------------------- target
    def set_config(self, chave: str, valor: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO fleet_config (chave,valor) VALUES (?,?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=?", (chave, valor, valor))
            self._conn.commit()

    def get_config(self, chave: str, default: str = "") -> str:
        with self._lock:
            r = self._conn.execute("SELECT valor FROM fleet_config WHERE chave=?", (chave,)).fetchone()
        return r["valor"] if r else default
