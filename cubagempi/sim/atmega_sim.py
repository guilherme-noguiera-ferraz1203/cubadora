"""Simulador da ponte ATmega/I²C (balança serial + GPIO).

Responde aos 'devices' como o firmware real:
- 15 (versão), 20/21 (serial da balança com checksum, frame Trentin), 22/23 (limpar buffer)
- 10 (entradas digitais), 255 (watchdog)
"""

from __future__ import annotations

from ..drivers.atmega_i2c import (
    CHECKSUM_CONST,
    DEV_INPUT_STATE,
    DEV_READ_VERSION,
    DEV_SERIAL_0_CHECKSUM,
    DEV_SERIAL_0_CLEAR,
    DEV_SERIAL_1_CHECKSUM,
    DEV_SERIAL_1_CLEAR,
    DEV_WATCHDOG,
    I2C_BUFFER_LENGTH,
)


class AtmegaSimulator:
    def __init__(self, peso: float = 2.17, casa_decimal_peso: float = 100.0,
                 versao: float = 3.4, estabilizado: bool = True, botao_reboot: bool = False):
        self.peso = peso
        self.casa_decimal_peso = casa_decimal_peso
        self.versao = versao
        self.estabilizado = estabilizado
        self.botao_reboot = botao_reboot

    def _trentin_frame(self) -> list[int]:
        """Frame Trentin de 8 bytes: [estado, 6 dígitos ASCII, STOP(13)]."""
        valor = int(round(self.peso * self.casa_decimal_peso))
        if valor < 0:
            estado = 76                              # 'L' negativo
        elif self.estabilizado:
            estado = 68                              # 'D' estabilizado
        else:
            estado = 64                              # '@' pesando
        digitos = f"{abs(valor):06d}"
        frame = [estado] + [ord(c) for c in digitos] + [13]
        return frame

    def handler(self, device: int, length: int) -> bytes:
        if device == DEV_WATCHDOG:
            return bytes(length)

        if device == DEV_READ_VERSION:
            v = int(round(self.versao * 10))
            return bytes([v // 256, v % 256] + [0] * (length - 2))

        if device in (DEV_SERIAL_0_CLEAR, DEV_SERIAL_1_CLEAR):
            return bytes([0, 1] + [0] * (length - 2))   # sucesso

        if device == DEV_INPUT_STATE:
            estado = 1 if self.botao_reboot else 0
            return bytes([0, estado] + [0] * (length - 2))

        if device in (DEV_SERIAL_0_CHECKSUM, DEV_SERIAL_1_CHECKSUM):
            frame = self._trentin_frame()
            data_length = len(frame)
            buf = [0] * I2C_BUFFER_LENGTH
            buf[0] = data_length
            for i, b in enumerate(frame):
                buf[i + 1] = b
            checksum = CHECKSUM_CONST + device + data_length + sum(frame)
            buf[30] = (checksum // 256) & 0xFF
            buf[31] = checksum % 256
            return bytes(buf[:length] if length <= len(buf) else buf + [0] * (length - len(buf)))

        return bytes(length)
