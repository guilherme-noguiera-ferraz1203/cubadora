"""Driver dos sensores ultrassônicos (protocolo proprietário de 5 bytes).

Porta direta de SensorDistanciaUltrasonico.java + SensorDistancia.java.

Frame TX/RX (5 bytes): [endereco, dataMsb, dataLsb, checksumMsb, checksumLsb]
  checksum = 1234 + endereco + dataMsb + dataLsb
Resposta:  valor = dataMsb*256 + dataLsb   (distância em DÉCIMOS DE MM)
           válida se enderecoRx == enderecoTx e checksumRx == checksum esperado

Códigos de erro retornados internamente: -1 timeout, -2 erro de checksum.
"""

from __future__ import annotations

import enum
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config.models import ConfigSensorDistancia
from ..hal.rs485 import Rs485
from .checksum import ultrasonic_checksum

log = logging.getLogger(__name__)

# Comandos (vão no byte dataMsb quando se usa o "endereço de comando" = grupo+100)
CMD_ECHO = 0
CMD_READ_VERSION = 1
CMD_GET_BAUDRATE_INDEX = 2
CMD_SET_BAUDRATE_INDEX = 3
CMD_READ_LM35_AVG = 10
CMD_READ_LM35_VALUE = 11

FRAME_LEN = 5
ERR_TIMEOUT = -1
ERR_CHECKSUM = -2

# Temperatura "default": se a configurada for diferente disto, aplica correção por temperatura.
DEFAULT_TEMPERATURA = 0.0


class IndexSensor(enum.IntEnum):
    """Sensores lógicos (índice = posição nos arrays de endereços)."""
    DIREITA = 0
    FUNDO = 1
    ESQUERDA = 2
    ALTURA = 3


# Ordem de varredura usada pelo Java (SensorDistancia.SEQUENCIA_LEITURA).
SequenciaLeitura = [IndexSensor.DIREITA, IndexSensor.FUNDO, IndexSensor.ESQUERDA, IndexSensor.ALTURA]


class SensorOutOfRangeError(Exception):
    """Alguma medida ficou fora da faixa configurada (min/max)."""


@dataclass
class _State:
    use_first_address: dict[int, bool] = field(default_factory=dict)
    error_count: int = 0
    timeout_count: int = 0
    log: str = ""


class UltrasonicSensor:
    def __init__(self, rs485: Rs485, config: ConfigSensorDistancia, rs485_timeout_ms: int = 50):
        self.rs485 = rs485
        self.config = config
        self.rs485_timeout_ms = rs485_timeout_ms
        self.s = _State()

    # ------------------------------------------------------------------ frames
    @staticmethod
    def build_frame(address: int, data_msb: int, data_lsb: int) -> bytes:
        cs = ultrasonic_checksum(address, data_msb & 0xFF, data_lsb & 0xFF)
        return bytes([
            address & 0xFF,
            data_msb & 0xFF,
            data_lsb & 0xFF,
            (cs // 256) & 0xFF,
            (cs % 256) & 0xFF,
        ])

    def _frame_distancia(self, address: int) -> bytes:
        data_msb = ((self.config.range_ultrasonico & 0x07) << 5) + (self.config.leituras_ultrasonico & 0x1F)
        data_lsb = self.config.delay_ultrasonico & 0xFF
        return self.build_frame(address, data_msb, data_lsb)

    @staticmethod
    def _address_command(address: int) -> int:
        """Endereço de comando = grupo+100 (11/12->101, 13/14->102, ...)."""
        mapping = {11: 101, 12: 101, 13: 102, 14: 102, 15: 103, 16: 103, 17: 104, 18: 104}
        return mapping.get(address, (address + 100) & 0xFF)

    # ------------------------------------------------------------- baixo nível
    def _transacao(self, frame: bytes, tentativas: int) -> int:
        """Envia um frame e devolve `valor` (>=0) ou ERR_TIMEOUT/ERR_CHECKSUM."""
        address_tx = frame[0]
        rx = self.rs485.write(frame, FRAME_LEN)
        if rx is not None and len(rx) == FRAME_LEN:
            address_rx = rx[0]
            data_rx = rx[1] * 256 + rx[2]
            cs_rx = rx[3] * 256 + rx[4]
            cs_exp = ultrasonic_checksum(rx[0], rx[1], rx[2])
            if address_rx == address_tx and cs_rx == cs_exp:
                return data_rx
            if tentativas > 1:
                time.sleep(self.rs485_timeout_ms / 1000.0)
                return self._transacao(frame, tentativas - 1)
            self.s.error_count += 1
            log.warning("Erro de checksum: addr=%d cs_rx=%d cs_exp=%d rx=%s",
                        address_tx, cs_rx, cs_exp, list(rx))
            return ERR_CHECKSUM
        if tentativas > 1:
            return self._transacao(frame, tentativas - 1)
        self.s.timeout_count += 1
        return ERR_TIMEOUT

    def read_raw(self, address: int) -> int:
        """Lê a distância bruta (décimos de mm) de um endereço físico."""
        return self._transacao(self._frame_distancia(address), self.config.tentativas)

    def read_version(self, address: int) -> float:
        v = self._transacao(self.build_frame(self._address_command(address), CMD_READ_VERSION, 0),
                            self.config.tentativas)
        return v / 10.0 if v > 0 else float(v)

    def read_temperatura(self) -> Optional[float]:
        addr = self.config.endereco_temperatura
        if not addr:
            return None
        frame = self.build_frame((addr + 100) & 0xFF, CMD_READ_LM35_AVG, 0)
        v = self._transacao(frame, max(2, self.config.tentativas))
        if v > 0:
            return v / 10.0 + self.config.ajuste_temperatura
        return None

    # ------------------------------------------------------------- distância (cm)
    @staticmethod
    def _corrigir_por_temperatura(raw: float, temperatura: float) -> float:
        duracao = raw * 58.0
        v_som = 331.45 * math.sqrt((temperatura + 273.15) / 273.15)
        us_por_cm = 1_000_000.0 / (v_som * 100.0)
        return duracao / (us_por_cm * 2.0)

    def read_distance_cm(self, address: int) -> float:
        """Distância em cm (ou valor negativo em caso de erro)."""
        if address == 0:
            return 0.0
        raw = float(self.read_raw(address))
        if raw > 0:
            temperatura = self.config.temperatura
            if temperatura and temperatura != DEFAULT_TEMPERATURA:
                raw = self._corrigir_por_temperatura(raw, temperatura)
            return raw / 10.0
        return raw  # -1 / -2

    # --------------------------------------------------------- sensores lógicos
    def is_dual(self, index: int) -> bool:
        return self.config.enderecos2[index] != 0

    def can_read(self, index: int) -> bool:
        return self.config.enderecos[index] != 0

    def read_sensor(self, index: int) -> float:
        """Lê um sensor lógico; alterna entre os dois endereços se for duplo."""
        addr1 = self.config.enderecos[index]
        addr2 = self.config.enderecos2[index]
        use_first = True
        if self.is_dual(index):
            use_first = self.s.use_first_address.get(index, True)
            self.s.use_first_address[index] = not use_first
        address = addr1 if use_first else addr2
        if address == 0:
            return 0.0
        return self.read_distance_cm(address)

    def ler_sensores(self, sequencia: list[IndexSensor] | None = None,
                     count_leituras: int | None = None) -> dict[IndexSensor, float]:
        """Varre os sensores `count_leituras` vezes e retorna a média filtrada por sensor."""
        sequencia = sequencia or SequenciaLeitura
        count_leituras = count_leituras or self.config.leituras

        leituras: dict[IndexSensor, list[float]] = {}
        t0 = time.monotonic()
        primeiro = True
        for _ in range(count_leituras):
            for idx in sequencia:
                if not self.can_read(int(idx)):
                    continue
                if not primeiro:
                    time.sleep(self.config.delay_sensores_ms / 1000.0)
                primeiro = False
                leituras.setdefault(idx, []).append(self.read_sensor(int(idx)))

        result = self._filtrar(leituras)
        log.info("Sensores: %d ms; %s",
                 int((time.monotonic() - t0) * 1000),
                 "; ".join(f"{k.name}={v:.2f}" for k, v in result.items()))
        return result

    def _filtrar(self, leituras: dict[IndexSensor, list[float]]) -> dict[IndexSensor, float]:
        result: dict[IndexSensor, float] = {}
        for idx, valores in leituras.items():
            dual = self.is_dual(int(idx))
            positivos: list[float] = []
            last: Optional[float] = None
            for v in valores:
                value: Optional[float] = v
                if dual:
                    # Em pares: pega o MENOR valor positivo dos dois endereços.
                    if last is None:
                        last, value = v, None
                    else:
                        if v > 0 and last > 0:
                            value = min(v, last)
                        elif last > 0:
                            value = last
                        last = None
                if value is not None and value > 0:
                    positivos.append(value)

            if len(positivos) >= 5:
                avg = (sum(positivos) - min(positivos) - max(positivos)) / (len(positivos) - 2)
            elif positivos:
                avg = sum(positivos) / len(positivos)
            else:
                avg = 0.0
            result[idx] = avg
        return result

    # ------------------------------------------------------------- validação
    def is_out_of_range(self, medidas: dict[IndexSensor, float]) -> bool:
        for idx, valor in medidas.items():
            i = int(idx)
            if valor is None:
                continue
            if valor < self.config.minimo_sensor[i] or valor > self.config.maximo_sensor[i]:
                log.warning("Sensor %s (%.2f cm) fora da faixa [%.1f, %.1f]",
                            idx.name, valor, self.config.minimo_sensor[i], self.config.maximo_sensor[i])
                return True
        return False
