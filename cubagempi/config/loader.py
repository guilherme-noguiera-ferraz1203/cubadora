"""Carregamento de configuração a partir de YAML, com fallback para os defaults.

A demo roda mesmo sem PyYAML/arquivo: nesse caso usa os valores default dos modelos.
"""

from __future__ import annotations

import logging
import os
from dataclasses import fields, is_dataclass
from typing import Any

from .models import AppConfig, ModeloMaquina

try:
    import yaml  # type: ignore
except ImportError:  # PyYAML é opcional para a demo
    yaml = None  # type: ignore

log = logging.getLogger(__name__)


def _overlay(obj: Any, data: dict) -> None:
    """Aplica um dict sobre um dataclass, somente em campos existentes."""
    if not isinstance(data, dict):
        return
    valid = {f.name for f in fields(obj)} if is_dataclass(obj) else set()
    for key, value in data.items():
        if key in valid:
            setattr(obj, key, value)


def load_config(path: str | None = None) -> AppConfig:
    cfg = AppConfig()

    if not path:
        return cfg
    if not os.path.exists(path):
        log.warning("Arquivo de configuração não encontrado: %s (usando defaults)", path)
        return cfg
    if yaml is None:
        log.warning("PyYAML não instalado; ignorando %s (usando defaults)", path)
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if "modelo_maquina" in data:
        cfg.modelo_maquina = ModeloMaquina(data["modelo_maquina"])
    for scalar in ("casa_decimal_medidas", "serial_maquina", "versao",
                   "nome_equipamento", "logo_path", "tema"):
        if scalar in data:
            setattr(cfg, scalar, data[scalar])
    for scalar in ("modo_teste", "totalizacao_peso"):
        if scalar in data:
            setattr(cfg, scalar, data[scalar])
    if "integracao" in data and isinstance(data["integracao"], list):
        cfg.integracao = data["integracao"]

    for section in SECOES:
        _overlay(getattr(cfg, section), data.get(section, {}))

    log.info("Configuração carregada de %s (modelo=%s)", path, cfg.modelo_maquina.value)
    return cfg


# Seções (sub-dataclasses) da configuração.
SECOES = ("rs485", "sensor", "ajustes", "balanca", "camera", "dinamica",
          "cloud", "web", "etiqueta", "calibracao", "login", "leitor", "lcd",
          "sorter", "atm", "frota", "kiosk")


def config_to_dict(cfg: AppConfig) -> dict:
    """Serializa a configuração para um dict (para a API web / salvar em YAML)."""
    d: dict = {
        "modelo_maquina": cfg.modelo_maquina.value,
        "casa_decimal_medidas": cfg.casa_decimal_medidas,
        "serial_maquina": cfg.serial_maquina,
        "versao": cfg.versao,
        "nome_equipamento": cfg.nome_equipamento,
        "logo_path": cfg.logo_path,
        "tema": cfg.tema,
        "modo_teste": cfg.modo_teste,
        "totalizacao_peso": cfg.totalizacao_peso,
    }
    for sec in SECOES:
        d[sec] = dict(getattr(cfg, sec).__dict__)
    d["integracao"] = cfg.integracao
    return d


def coerce(atual, valor):
    """Converte `valor` (vindo da web) para o tipo do campo atual."""
    if isinstance(atual, bool):
        return str(valor).strip().lower() in ("1", "true", "on", "yes", "sim")
    if isinstance(atual, int) and not isinstance(atual, bool):
        return int(float(valor))
    if isinstance(atual, float):
        return float(valor)
    if isinstance(atual, list):
        return valor if isinstance(valor, list) else atual
    return valor


def save_config(cfg: AppConfig, path: str) -> None:
    """Salva a configuração em YAML (requer PyYAML)."""
    if yaml is None:
        raise RuntimeError("PyYAML não instalado; não é possível salvar a configuração")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_to_dict(cfg), f, sort_keys=False, allow_unicode=True)
    log.info("Configuração salva em %s", path)
