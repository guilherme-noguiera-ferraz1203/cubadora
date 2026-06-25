"""Cliente REST de integração com o ERP (porta de RestClient.java).

Monta o JSON a partir do template do config (substituindo $etiqueta/$altura/$largura/
$comprimento/$peso/$data), envia via POST com os headers configurados (ex.: Bearer) e
valida a resposta contra o `success-tag`. Usa urllib (stdlib, sem dependências).
"""

from __future__ import annotations

import logging
import urllib.request
from datetime import datetime

from ..cubagem import Cubagem

log = logging.getLogger(__name__)

HEADER_PREFIX = "header-"
PARAMS_TARGET = ("$etiqueta", "$altura", "$largura", "$comprimento", "$peso")
PARAMS_JSON = ("$etiqueta", "$altura", "$largura", "$comprimento", "$peso", "$data")


class IntegracaoError(Exception):
    pass


def _format_param(param: str, etiqueta: str, cub: Cubagem, item: dict, casa_decimal: int, data_str: str) -> str:
    if param == "$etiqueta":
        return etiqueta
    if param == "$data":
        return data_str
    if param == "$peso":
        fator = float(item.get("peso-fator", 1))
        fmt = item.get("peso-format", "%.2f")
        return fmt % (cub.peso * fator)
    valores = {"$altura": cub.altura, "$largura": cub.largura, "$comprimento": cub.comprimento}
    fator = float(item.get("medida-fator", 1))
    fmt = item.get("medida-format", "%.2f")
    val = (valores[param] / casa_decimal) * fator
    return fmt % val


class RestClient:
    def render(self, etiqueta: str, cub: Cubagem, item: dict, casa_decimal: int) -> tuple[str, str, dict]:
        data_str = datetime.now().isoformat()
        target = item.get("$target") or item.get("target", "")
        for p in PARAMS_TARGET:
            target = target.replace(p, _format_param(p, etiqueta, cub, item, casa_decimal, data_str))

        body = item.get("json", "")
        if body.startswith("{"):
            for p in PARAMS_JSON:
                body = body.replace(p, _format_param(p, etiqueta, cub, item, casa_decimal, data_str))

        headers = {"Content-Type": "application/json"}
        for k, v in item.items():
            if k.startswith(HEADER_PREFIX):
                headers[k[len(HEADER_PREFIX):]] = v
        accept = item.get("accept-media-type")
        if accept:
            headers["Accept"] = accept
        return target, body, headers

    def post(self, url: str, body: str, headers: dict, timeout_ms: int, success_tag: str) -> str:
        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0) as resp:
            resposta = resp.read().decode("utf-8", "replace")
        if success_tag and success_tag != "*" and success_tag not in resposta:
            raise IntegracaoError(f"Resposta sem success-tag '{success_tag}': {resposta[:200]}")
        log.info("Integração OK: %s", resposta[:200])
        return resposta

    def execute(self, etiqueta: str, cub: Cubagem, item: dict, casa_decimal: int) -> str:
        url, body, headers = self.render(etiqueta, cub, item, casa_decimal)
        timeout = int(item.get("timeout", 5000))
        success = item.get("success-tag", "*")
        log.info("Integração POST %s | body=%s", url, body)
        return self.post(url, body, headers, timeout, success)
