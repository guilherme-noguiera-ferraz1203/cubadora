"""Integrações externas (ERP via REST e nuvem Compudeck)."""

from .rest_client import RestClient, IntegracaoError
from .manager import IntegracaoManager
from .cloud import CloudClient

__all__ = ["RestClient", "IntegracaoError", "IntegracaoManager", "CloudClient"]
