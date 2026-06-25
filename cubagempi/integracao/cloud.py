"""Cliente da nuvem Compudeck (envio de cubagens, config, atualização).

Esqueleto best-effort: por segurança vem DESABILITADO por padrão (não envia nada à nuvem
real sem ser explicitamente ligado). Os endpoints exatos podem ser ajustados conforme a API.
"""

from __future__ import annotations

import json as jsonlib
import logging
import urllib.request

from ..config.models import ConfigCloud
from ..cubagem import Cubagem

log = logging.getLogger(__name__)


class CloudClient:
    def __init__(self, config: ConfigCloud, serial_maquina: str = "", habilitada: bool = False):
        self.config = config
        self.serial_maquina = serial_maquina
        self.habilitada = habilitada

    def enviar_cubagem(self, etiqueta: str, cub: Cubagem) -> bool:
        if not self.habilitada:
            log.debug("Nuvem desabilitada; ignorando envio de %s", etiqueta)
            return False
        url = f"{self.config.target_secure}/cubagem"
        payload = jsonlib.dumps({
            "serial": self.serial_maquina, "etiqueta": etiqueta,
            "altura": cub.altura, "largura": cub.largura,
            "comprimento": cub.comprimento, "peso": cub.peso,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao enviar para a nuvem: %s", exc)
            return False

    def baixar_config(self) -> bool:
        """Baixa a configuração da nuvem (best-effort)."""
        if not self.habilitada:
            log.debug("Nuvem desabilitada; ignorando download de config")
            return False
        url = f"{self.config.target_secure}/config/{self.serial_maquina}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                resp.read()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao baixar config da nuvem: %s", exc)
            return False

    def registrar(self, chave: str = "") -> bool:
        """Registra a máquina na nuvem (serial + chave)."""
        if not self.habilitada:
            return False
        url = f"{self.config.target_secure}/registro"
        payload = jsonlib.dumps({"serial": self.serial_maquina, "chave": chave}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            return True
        except Exception:  # noqa: BLE001
            return False
