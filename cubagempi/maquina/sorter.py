"""Sorter / classificador de esteira (porta de Sorter/StatusSorter/HistoricoSorter/CountEsteira).

Encaminha cada volume para um destino (lane). O destino é enviado a um controlador via Modbus
(registro de destino) ou por comando bruto "*485 <end> <reg> <val>".
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from ..config.models import ConfigSorter
from ..drivers.modbus import Modbus485

log = logging.getLogger(__name__)


@dataclass
class HistoricoSorter:
    registros: list[dict] = field(default_factory=list)

    def add(self, etiqueta: str, destino: int) -> None:
        self.registros.append({"etiqueta": etiqueta, "destino": destino})
        if len(self.registros) > 1000:
            self.registros.pop(0)


class CountEsteira:
    def __init__(self) -> None:
        self.por_destino: dict[int, int] = defaultdict(int)

    def add(self, destino: int) -> None:
        self.por_destino[destino] += 1

    def total(self) -> int:
        return sum(self.por_destino.values())


class Sorter:
    def __init__(self, modbus: Modbus485, config: ConfigSorter):
        self.modbus = modbus
        self.config = config
        self.historico = HistoricoSorter()
        self.contagem = CountEsteira()

    def enviar(self, etiqueta: str, destino: int) -> None:
        """Encaminha o volume para um destino (lane)."""
        if self.config.enabled:
            self.modbus.write("Sorter destino", self.config.endereco_clp,
                              self.config.registro_destino, destino)
        self.historico.add(etiqueta, destino)
        self.contagem.add(destino)
        log.info("Sorter: etiqueta=%s -> destino=%d", etiqueta, destino)

    def enviar_raw(self, comando: str) -> str:
        """Comando bruto '*485 <endereco> <registro> <valor>'."""
        partes = comando.replace("*485", "").split()
        if len(partes) >= 3:
            end, reg, val = int(partes[0]), int(partes[1]), int(partes[2])
            self.modbus.write("Sorter raw", end, reg, val)
            return f"Sorter: escrito {val} no registro {reg} (end {end})"
        return "Uso: *485 <endereco> <registro> <valor>"

    def status(self) -> dict:
        return {"total": self.contagem.total(), "por_destino": dict(self.contagem.por_destino)}
