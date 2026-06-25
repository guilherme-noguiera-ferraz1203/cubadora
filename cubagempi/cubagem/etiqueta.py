"""Parsing da etiqueta lida (porta de ConfigEtiqueta + DANFE + CEP).

Extrai campos da string da etiqueta (código de barras), seja por regex, por posição/tamanho,
ou interpretando a chave de NF-e (DANFE, 44 dígitos).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ..config.models import ConfigEtiqueta

log = logging.getLogger(__name__)


@dataclass
class EtiquetaInfo:
    texto: str = ""
    nota: str = ""
    cnpj: str = ""
    quantidade_volumes: int = 1
    numero_volume: int = 1
    cep: str = ""
    extra: dict = field(default_factory=dict)


def _sub(texto: str, pos: int, tam: int) -> str:
    return texto[pos:pos + tam] if tam > 0 else ""


def parse_danfe(chave: str) -> EtiquetaInfo:
    """Interpreta a chave de acesso da NF-e (44 dígitos).

    Layout: cUF(2) AAMM(4) CNPJ(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) cDV(1)
    """
    info = EtiquetaInfo(texto=chave)
    digitos = re.sub(r"\D", "", chave)
    if len(digitos) == 44:
        info.cnpj = digitos[6:20]
        info.nota = str(int(digitos[25:34]))  # nNF sem zeros à esquerda
    else:
        info.nota = chave
    return info


def parse_etiqueta(texto: str, cfg: ConfigEtiqueta) -> EtiquetaInfo:
    texto = (texto or "").strip()

    if cfg.danfe:
        return parse_danfe(texto)

    info = EtiquetaInfo(texto=texto, nota=texto)

    if cfg.regex:
        m = re.search(cfg.regex, texto)
        if m:
            gd = m.groupdict()
            info.nota = gd.get("nota", info.nota)
            info.cnpj = gd.get("cnpj", "")
            info.cep = gd.get("cep", "")
            if gd.get("quantidade_volumes"):
                info.quantidade_volumes = int(re.sub(r"\D", "", gd["quantidade_volumes"]) or 1)
            if gd.get("numero_volume"):
                info.numero_volume = int(re.sub(r"\D", "", gd["numero_volume"]) or 1)
            info.extra = gd
        return info

    # Por posição/tamanho fixos
    if cfg.tamanho_nota > 0:
        info.nota = _sub(texto, cfg.posicao_nota, cfg.tamanho_nota)
    if cfg.tamanho_cnpj > 0:
        info.cnpj = _sub(texto, cfg.posicao_cnpj, cfg.tamanho_cnpj)
    if cfg.tamanho_quantidade_volumes > 0:
        q = re.sub(r"\D", "", _sub(texto, cfg.posicao_quantidade_volumes, cfg.tamanho_quantidade_volumes))
        info.quantidade_volumes = int(q or 1)
    if cfg.tamanho_numero_volume > 0:
        n = re.sub(r"\D", "", _sub(texto, cfg.posicao_numero_volume, cfg.tamanho_numero_volume))
        info.numero_volume = int(n or 1)
    if cfg.modo_cep and cfg.tamanho_cep > 0:
        info.cep = _sub(texto, 0, cfg.tamanho_cep)
    return info
