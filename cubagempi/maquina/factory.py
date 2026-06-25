"""Factory: escolhe a máquina pelo modelo configurado (porta de MaquinaFactory.java)."""

from __future__ import annotations

from ..config.models import AppConfig, ModeloMaquina
from .atm import MaquinaAtm
from .base import Maquina
from .camera_maquina import MaquinaCamera
from .dinamica import MaquinaDinamica
from .estatica import MaquinaEstatica
from .hardware import Hardware


def create_maquina(hardware: Hardware, config: AppConfig) -> Maquina:
    modelo = config.modelo_maquina
    if modelo in (ModeloMaquina.DINAMICA_PI, ModeloMaquina.DINAMICA_CLP):
        return MaquinaDinamica(hardware, config)
    if modelo == ModeloMaquina.ATM:
        return MaquinaAtm(hardware, config)
    if modelo == ModeloMaquina.CAMERA:
        return MaquinaCamera(hardware, config)
    return MaquinaEstatica(hardware, config)
