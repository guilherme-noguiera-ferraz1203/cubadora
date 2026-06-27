"""Banco do servidor de frota (SQLite): equipamentos, eventos/erros e versão-alvo."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta

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
CREATE TABLE IF NOT EXISTS command (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT,
    tipo        TEXT,
    parametros  TEXT,
    status      TEXT DEFAULT 'pendente',
    resultado   TEXT,
    criado_em   TEXT,
    enviado_em  TEXT,
    ack_em      TEXT
);
"""


class FleetDB:
    def __init__(self, path: str = "fleet.db"):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Migração de colunas do device (cada uma é segura/idempotente)
            cols = [r["name"] for r in self._conn.execute("PRAGMA table_info(device)").fetchall()]
            if "versao_alvo" not in cols:
                self._conn.execute("ALTER TABLE device ADD COLUMN versao_alvo TEXT")
            if "estado" not in cols:
                # snapshot completo do device (status_dict + sistema_info + ultimo diagnostico) em JSON
                self._conn.execute("ALTER TABLE device ADD COLUMN estado TEXT")
            if "tunnel_port" not in cols:
                # Porta TCP unica alocada por device para o tunel reverso SSH (autossh).
                self._conn.execute("ALTER TABLE device ADD COLUMN tunnel_port INTEGER")
            if "tunnel_pubkey" not in cols:
                # Chave publica SSH (ed25519) que o Pi usa para abrir o tunel reverso.
                self._conn.execute("ALTER TABLE device ADD COLUMN tunnel_pubkey TEXT")
            if "placa" not in cols:
                # Modelo da placa Raspberry escolhido no cadastro (pi3 | pi4 | pi5).
                # Influencia os pacotes apt e python instalados pelo bootstrap.
                self._conn.execute("ALTER TABLE device ADD COLUMN placa TEXT")
            if "modelo_maquina" not in cols:
                # Tipo do equipamento (ESTATICA_2, DINAMICA_PI, etc.) gravado no config.yaml.
                self._conn.execute("ALTER TABLE device ADD COLUMN modelo_maquina TEXT")
            self._conn.commit()

    # --------------------------------------------------------------- devices
    def upsert_device(self, p: dict) -> None:
        agora = datetime.now().isoformat()
        with self._lock:
            existe = self._conn.execute("SELECT device_id FROM device WHERE device_id=?",
                                        (p.get("device_id"),)).fetchone()
            estado_in = p.get("estado")
            estado_str = json.dumps(estado_in) if estado_in else None
            if existe:
                # Se o heartbeat trouxe estado novo, atualiza; senão preserva o ultimo.
                if estado_str is not None:
                    self._conn.execute(
                        "UPDATE device SET nome=?,unidade=?,versao=?,modelo=?,ip=?,status=?,status_cor=?,"
                        "aferido=?,integracao=?,producao=?,last_seen=?,estado=? WHERE device_id=?",
                        (p.get("nome"), p.get("unidade"), p.get("versao"), p.get("modelo"), p.get("ip"),
                         p.get("status"), p.get("status_cor"), 1 if p.get("aferido") else 0,
                         p.get("integracao"), json.dumps(p.get("producao") or {}), agora, estado_str, p.get("device_id")))
                else:
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
            # estado nao precisa ir na listagem (so no detalhe); economiza payload
            d.pop("estado", None)
            out.append(d)
        return out

    def get_device(self, device_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["producao"] = json.loads(d.get("producao") or "{}")
        if d.get("estado"):
            try:
                d["estado"] = json.loads(d["estado"])
            except (TypeError, ValueError):
                d["estado"] = None
        return d

    def delete_device(self, device_id: str) -> dict:
        """Remove o equipamento + TODOS os dados associados (events, commands, chave do tunel).
        Operacao irreversivel — botao 'Remover equipamento' do painel."""
        with self._lock:
            n_dev = self._conn.execute("DELETE FROM device WHERE device_id=?", (device_id,)).rowcount
            n_evt = self._conn.execute("DELETE FROM event WHERE device_id=?", (device_id,)).rowcount
            n_cmd = self._conn.execute("DELETE FROM command WHERE device_id=?", (device_id,)).rowcount
            self._conn.commit()
        return {"device": n_dev, "eventos": n_evt, "comandos": n_cmd}

    def create_pending_device(self, device_id: str, nome: str, unidade: str,
                              placa: str = "", modelo_maquina: str = "") -> bool:
        """Pré-cadastra um equipamento. Ele aparece no painel como 'aguardando instalação'
        (last_seen NULL) até o primeiro heartbeat. Retorna False se o device_id já existir.
        `placa` (pi3|pi4|pi5) e `modelo_maquina` (ESTATICA_2, DINAMICA_PI, ...) sao gravados
        pra customizar o script de instalacao."""
        agora = datetime.now().isoformat()
        with self._lock:
            existe = self._conn.execute("SELECT device_id FROM device WHERE device_id=?",
                                        (device_id,)).fetchone()
            if existe:
                return False
            self._conn.execute(
                "INSERT INTO device (device_id,nome,unidade,placa,modelo_maquina,primeiro_seen) "
                "VALUES (?,?,?,?,?,?)",
                (device_id, nome, unidade, placa, modelo_maquina, agora))
            self._conn.commit()
        return True

    def alloc_tunnel_port(self, device_id: str, base: int = 19000) -> int:
        """Aloca (ou retorna a existente) a porta TCP do tunel reverso desse equipamento.
        Cada device tem uma porta unica (>= base) para o autossh fazer -R <port>:127.0.0.1:8080."""
        with self._lock:
            r = self._conn.execute("SELECT tunnel_port FROM device WHERE device_id=?", (device_id,)).fetchone()
            if r and r["tunnel_port"]:
                return int(r["tunnel_port"])
            mx = self._conn.execute("SELECT MAX(tunnel_port) FROM device").fetchone()[0] or (base - 1)
            nova = max(int(mx) + 1, base)
            self._conn.execute("UPDATE device SET tunnel_port=? WHERE device_id=?", (nova, device_id))
            self._conn.commit()
            return nova

    def set_tunnel_pubkey(self, device_id: str, pubkey: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE device SET tunnel_pubkey=? WHERE device_id=?", (pubkey.strip(), device_id))
            self._conn.commit()

    def list_tunnels(self) -> list[dict]:
        """Todos os devices com tunnel registrado — usado para gerar authorized_keys."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT device_id, tunnel_port, tunnel_pubkey FROM device "
                "WHERE tunnel_port IS NOT NULL AND tunnel_pubkey IS NOT NULL AND tunnel_pubkey != ''"
            ).fetchall()
        return [dict(r) for r in rows]

    def set_device_target(self, device_id: str, versao: str) -> None:
        """Define a versão-alvo DESTE equipamento (update ou rollback). Vazio = não atualizar."""
        with self._lock:
            self._conn.execute("UPDATE device SET versao_alvo=? WHERE device_id=?", (versao, device_id))
            self._conn.commit()

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

    def clear_events(self, device_id: str) -> int:
        """Remove TODO o historico de eventos de um equipamento (botao 'limpar' no painel)."""
        with self._lock:
            n = self._conn.execute("DELETE FROM event WHERE device_id=?", (device_id,)).rowcount
            self._conn.commit()
        return n

    def prune_events(self, max_por_device: int = 500, max_dias: int = 30) -> int:
        """Retencao automatica: mantem so os ultimos N eventos por device, e descarta os > max_dias.
        Roda periodicamente pra evitar que o banco cresca indefinidamente."""
        agora = datetime.now()
        corte = (agora.replace(microsecond=0) - timedelta(days=max_dias)).isoformat()
        with self._lock:
            n_velhos = self._conn.execute("DELETE FROM event WHERE data < ?", (corte,)).rowcount
            # mantem so os ultimos max_por_device por device
            self._conn.execute(
                "DELETE FROM event WHERE id NOT IN ("
                "  SELECT id FROM event e WHERE id IN ("
                "    SELECT id FROM event WHERE device_id=e.device_id ORDER BY id DESC LIMIT ?"
                "  )"
                ")", (max_por_device,))
            n_extras = self._conn.total_changes - n_velhos
            self._conn.commit()
        return n_velhos + max(0, n_extras)

    # --------------------------------------------------------------- commands
    def add_command(self, device_id: str, tipo: str, parametros: dict | None = None) -> int:
        """Enfileira um comando para o equipamento. Retorna o id do comando."""
        agora = datetime.now().isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO command (device_id,tipo,parametros,status,criado_em) VALUES (?,?,?,?,?)",
                (device_id, tipo, json.dumps(parametros or {}), "pendente", agora))
            self._conn.commit()
            return cur.lastrowid

    def pull_commands(self, device_id: str) -> list[dict]:
        """Entrega os comandos pendentes do equipamento e os marca como 'enviado' (entrega única,
        evita reexecução/loop em comandos destrutivos). Resultado vem depois via ack_command()."""
        agora = datetime.now().isoformat()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,tipo,parametros FROM command WHERE device_id=? AND status='pendente' ORDER BY id",
                (device_id,)).fetchall()
            if rows:
                ids = [r["id"] for r in rows]
                self._conn.execute(
                    "UPDATE command SET status='enviado', enviado_em=? WHERE id IN (%s)"
                    % ",".join("?" * len(ids)), [agora, *ids])
                self._conn.commit()
        return [{"id": r["id"], "tipo": r["tipo"], "parametros": json.loads(r["parametros"] or "{}")} for r in rows]

    def ack_command(self, command_id: int, status: str, resultado: str = "") -> None:
        """Registra o resultado de um comando reportado pelo equipamento."""
        agora = datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE command SET status=?, resultado=?, ack_em=? WHERE id=?",
                (status or "executado", resultado, agora, command_id))
            self._conn.commit()

    def list_commands(self, device_id: str, limit: int = 15) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,tipo,parametros,status,resultado,criado_em,ack_em FROM command "
                "WHERE device_id=? ORDER BY id DESC LIMIT ?", (device_id, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["parametros"] = json.loads(d.get("parametros") or "{}")
            out.append(d)
        return out

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
