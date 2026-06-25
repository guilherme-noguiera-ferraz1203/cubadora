"""Drivers de balança de alto nível (porta de Balanca.java / BalancaAtmegaI2C / Balanca485)."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from ..config.models import ConfigBalanca
from .atmega_i2c import AtmegaI2C, DEV_SERIAL_0_CHECKSUM, DEV_SERIAL_0_OLD
from .modbus import Modbus485
from .scale_protocol import DelimitedBuffer, Trentin, Weightech

log = logging.getLogger(__name__)


class Balanca(ABC):
    """Base das balanças seriais (lê peso estabilizado a partir de frames Trentin/Weightech)."""

    PESO_TENTATIVAS = 3
    PESO_LEITURAS = 5

    def __init__(self, casa_decimal_peso: float = 100.0):
        self.casa_decimal_peso = casa_decimal_peso
        self._estabilizado = False
        self.debug_mode = False

    @abstractmethod
    def _get_buffer_rx(self) -> Optional[list[int]]: ...

    @abstractmethod
    def _serial_delay_ms(self) -> int: ...

    def _get_peso(self) -> float:
        buf = self._get_buffer_rx()
        if buf is None:
            if self.debug_mode:
                return 0.0
            raise RuntimeError("Balanca: nenhum buffer válido recebido pela serial")
        for i in range(len(buf)):
            if Trentin.exists_peso(buf, i):
                peso = Trentin.parse_peso(buf, i) / self.casa_decimal_peso
                if buf[i] == Trentin.START_ESTABILIZADO:
                    self._estabilizado = True
                elif buf[i] == Trentin.START_NEGATIVO:
                    peso *= -1.0
                return peso
            if Weightech.exists_peso(buf, i):
                return Weightech.parse_peso(buf, i) / self.casa_decimal_peso
        raise ValueError("Peso inválido")

    def get_media_peso(self) -> float:
        """Lê até obter um peso estabilizado; senão a média de 5 leituras (porta de getMediaPeso)."""
        for _ in range(self.PESO_TENTATIVAS):
            try:
                self._estabilizado = False
                soma = 0.0
                for _ in range(self.PESO_LEITURAS):
                    time.sleep(self._serial_delay_ms() / 1000.0)
                    peso = self._get_peso()
                    if self._estabilizado:
                        return peso
                    soma += peso
                return soma / self.PESO_LEITURAS
            except Exception:  # noqa: BLE001
                log.exception("Erro ao ler o peso")
        return 0.0


class BalancaAtmegaI2C(Balanca):
    """Balança lida pela ponte ATmega via I²C (modelos estáticos)."""

    def __init__(self, atmega: AtmegaI2C, config: ConfigBalanca):
        super().__init__(config.casa_decimal_peso)
        self.atmega = atmega
        self.serial_device = config.i2c_serial_device
        self._delimited = DelimitedBuffer(Trentin.START_BYTES, Trentin.STOP_BYTE, False)

    def _serial_delay_ms(self) -> int:
        return 100

    def _get_buffer_rx(self) -> Optional[list[int]]:
        for tentativas in range(3):
            if tentativas > 0:
                time.sleep(0.1)
            novo = self.atmega.read_device_serial(self.serial_device)
            result = self._delimited.process(novo)
            if result is not None:
                return result
        return None

    def get_media_peso(self) -> float:
        self.atmega.clear_serial_buffer(self.serial_device, 3)
        self._delimited.clear()
        return super().get_media_peso()


class Balanca485:
    """Balança via Modbus RTU (modelos dinâmicos). Endereço/registro vêm do config."""

    REGISTRO_PESO_INSTANTANEO = 2

    def __init__(self, modbus: Modbus485, config: ConfigBalanca):
        self.modbus = modbus
        self.config = config

    def read_peso(self) -> float:
        valor = self.modbus.read("Peso", self.config.endereco, self.config.registro_peso)
        peso = valor / self.config.casa_decimal_peso + self.config.ajuste_peso
        return max(peso, self.config.peso_minimo)

    def read_peso_instantaneo(self) -> float:
        valor = self.modbus.read("Peso instantaneo", self.config.endereco, self.REGISTRO_PESO_INSTANTANEO)
        return valor / self.config.casa_decimal_peso

    def get_media_peso(self) -> float:
        """Alias unificado com a interface da balança serial."""
        return self.read_peso()
