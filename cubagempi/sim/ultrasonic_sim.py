"""Simulador dos sensores ultrassônicos no barramento RS-485.

Responde a frames de 5 bytes como o firmware real:
- leitura de distância (endereços 11..18) -> devolve a distância configurada (+ ruído opcional)
- comandos (endereço >= 100): versão, temperatura, echo, baudrate

Uso:
    sim = UltrasonicSimulator(distancias={11: 1074, 12: 1068, ...})
    rs485 = MockRs485(sim.responder)
"""

from __future__ import annotations

from typing import Optional

from ..drivers.checksum import ultrasonic_checksum
from ..drivers.ultrasonic import (
    CMD_ECHO,
    CMD_GET_BAUDRATE_INDEX,
    CMD_READ_LM35_AVG,
    CMD_READ_LM35_VALUE,
    CMD_READ_VERSION,
    CMD_SET_BAUDRATE_INDEX,
)


class UltrasonicSimulator:
    def __init__(
        self,
        distancias: dict[int, int] | None = None,
        versao_firmware: float = 3.2,
        temperatura: float = 19.9,
        ruido: int = 0,
    ) -> None:
        # Distâncias em décimos de mm (mesma unidade do firmware). Ex.: 250 = 25,0 cm.
        # Cenário padrão: uma caixa ~ 78 x 37 x 31 cm sobre a plataforma.
        # (uma plataforma VAZIA leria perto do máximo de cada sensor, ex.: DIREITA ~ 1070.)
        self.distancias = distancias or {
            11: 255, 12: 250,     # DIREITA  -> 25,0 cm
            13: 288, 14: 288,     # FUNDO    -> 28,8 cm
            15: 255, 16: 250,     # ESQUERDA -> 25,0 cm
            17: 463, 18: 453,     # ALTURA   -> 45,3 cm
        }
        self.versao_firmware = versao_firmware
        self.temperatura = temperatura
        self.ruido = ruido
        self._n = 0  # contador para gerar uma pequena variação determinística

    def _build_response(self, address: int, valor: int) -> bytes:
        valor &= 0xFFFF
        data_msb = valor // 256
        data_lsb = valor % 256
        cs = ultrasonic_checksum(address, data_msb, data_lsb)
        return bytes([address & 0xFF, data_msb, data_lsb, (cs // 256) & 0xFF, (cs % 256) & 0xFF])

    def responder(self, tx: bytes, length_rx: int) -> Optional[bytes]:
        if len(tx) != 5:
            return None
        address, data_msb, data_lsb = tx[0], tx[1], tx[2]

        # Comandos usam o "endereço de comando" (>= 100).
        if address >= 100:
            if data_msb == CMD_READ_VERSION:
                return self._build_response(address, int(round(self.versao_firmware * 10)))
            if data_msb in (CMD_READ_LM35_AVG, CMD_READ_LM35_VALUE):
                return self._build_response(address, int(round(self.temperatura * 10)))
            if data_msb == CMD_ECHO:
                return self._build_response(address, 123)
            if data_msb in (CMD_GET_BAUDRATE_INDEX, CMD_SET_BAUDRATE_INDEX):
                return self._build_response(address, data_lsb)  # ecoa o índice
            return self._build_response(address, 0)

        # Leitura de distância.
        if address in self.distancias:
            valor = self.distancias[address]
            if self.ruido:
                self._n += 1
                valor += (self._n % (2 * self.ruido + 1)) - self.ruido
            return self._build_response(address, max(0, valor))

        # Endereço inexistente -> timeout (sem resposta).
        return None
