"""Hardware Abstraction Layer (HAL).

Cada recurso de hardware tem uma interface e duas implementações:
- real (Raspberry Pi)
- mock/simulada (PC, para desenvolvimento e testes)
"""

from .gpio import OutputPin, MockOutputPin, create_output_pin
from .rs485 import Rs485, MockRs485, Responder, create_rs485
from .i2c import I2CBus, MockI2C, create_i2c

__all__ = [
    "OutputPin", "MockOutputPin", "create_output_pin",
    "Rs485", "MockRs485", "Responder", "create_rs485",
    "I2CBus", "MockI2C", "create_i2c",
]
