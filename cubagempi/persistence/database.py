"""Banco de dados local em SQLite (cubagens, contadores e fila de integração).

Substitui o ObjectDB do sistema Java. Thread-safe (as máquinas rodam em threads).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cubagem (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    etiqueta    TEXT,
    altura      REAL,
    largura     REAL,
    comprimento REAL,
    peso        REAL,
    volume      REAL,
    data        TEXT,
    enviado     INTEGER DEFAULT 0,
    integracao  TEXT DEFAULT 'pendente'
);
CREATE TABLE IF NOT EXISTS contador (
    chave TEXT PRIMARY KEY,
    valor INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS integracao_fila (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    etiqueta   TEXT,
    payload    TEXT,
    target     TEXT,
    status     TEXT DEFAULT 'pendente',
    tentativas INTEGER DEFAULT 0,
    data       TEXT
);
"""


class Database:
    def __init__(self, path: str = "cubagem.db"):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # migração: adiciona a coluna 'integracao' em bancos antigos
            try:
                self._conn.execute("ALTER TABLE cubagem ADD COLUMN integracao TEXT DEFAULT 'pendente'")
            except sqlite3.OperationalError:
                pass  # já existe
            self._conn.commit()
        log.info("Banco de dados aberto: %s", path)

    # ----------------------------------------------------------------- cubagem
    def salvar_cubagem(self, etiqueta: str, altura: float, largura: float,
                       comprimento: float, peso: float, volume: float) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO cubagem (etiqueta, altura, largura, comprimento, peso, volume, data) "
                "VALUES (?,?,?,?,?,?,?)",
                (etiqueta, altura, largura, comprimento, peso, volume, datetime.now().isoformat()),
            )
            self._conn.commit()
            return cur.lastrowid

    def listar_cubagens(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM cubagem ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def ultima_cubagem(self) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM cubagem ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def contar_cubagens_desde(self, iso_inicio: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM cubagem WHERE data >= ?", (iso_inicio,)
            ).fetchone()
        return row["n"] if row else 0

    def limpar_cubagens(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cubagem")
            self._conn.commit()

    def atualizar_integracao(self, id_: int, status: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE cubagem SET integracao = ? WHERE id = ?", (status, id_))
            self._conn.commit()

    # --------------------------------------------------------------- contadores
    def inc_contador(self, chave: str, valor: int = 1) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO contador (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = valor + ?",
                (chave, valor, valor),
            )
            self._conn.commit()

    def get_contador(self, chave: str) -> int:
        with self._lock:
            row = self._conn.execute("SELECT valor FROM contador WHERE chave = ?", (chave,)).fetchone()
        return row["valor"] if row else 0

    def todos_contadores(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute("SELECT chave, valor FROM contador").fetchall()
        return {r["chave"]: r["valor"] for r in rows}

    # ------------------------------------------------------------ fila integração
    def enfileirar_integracao(self, etiqueta: str, payload: str, target: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO integracao_fila (etiqueta, payload, target, data) VALUES (?,?,?,?)",
                (etiqueta, payload, target, datetime.now().isoformat()),
            )
            self._conn.commit()
            return cur.lastrowid

    def integracoes_pendentes(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM integracao_fila WHERE status = 'pendente' ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def marcar_integracao(self, id_: int, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE integracao_fila SET status = ?, tentativas = tentativas + 1 WHERE id = ?",
                (status, id_),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
