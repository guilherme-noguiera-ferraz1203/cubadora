#!/usr/bin/env python3
"""Demo: lê os sensores ultrassônicos e calcula as dimensões.

PC (simulado):   python scripts/read_sensors.py
PC com config:   python scripts/read_sensors.py --config config.example.yaml
Raspberry Pi:    python scripts/read_sensors.py --config /home/pi/cubagem-pi/config.yaml --real
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Permite rodar o script direto (sem instalar o pacote).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cubagempi.config import load_config
from cubagempi.core import setup_logging
from cubagempi.cubagem import altura_com_ajuste, comprimento_com_ajuste, largura_com_ajuste, Cubagem
from cubagempi.drivers.ultrasonic import IndexSensor, UltrasonicSensor
from cubagempi.hal.rs485 import create_rs485
from cubagempi.sim import UltrasonicSimulator


def main() -> int:
    parser = argparse.ArgumentParser(description="Leitura de sensores ultrassônicos + dimensões")
    parser.add_argument("--config", help="caminho do config.yaml (opcional)")
    parser.add_argument("--real", action="store_true", help="usa hardware real (Raspberry Pi)")
    parser.add_argument("--debug", action="store_true", help="log em nível DEBUG")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)
    cfg = load_config(args.config)

    if args.real:
        rs485 = create_rs485(cfg.rs485, real=True)
    else:
        sim = UltrasonicSimulator(ruido=2)
        rs485 = create_rs485(cfg.rs485, responder=sim.responder)
        print(">> Modo SIMULADO (sem hardware). Use --real no Raspberry Pi.\n")

    sensor = UltrasonicSensor(rs485, cfg.sensor, cfg.rs485.timeout_ms)

    # Versões/temperatura (diagnóstico).
    if not args.real:
        print(f"Versão firmware (sim): {sensor.read_version(11)}")
    temp = sensor.read_temperatura()
    if temp is not None:
        print(f"Temperatura: {temp:.1f} °C")

    # Varredura completa.
    medidas = sensor.ler_sensores()
    print("\nDistâncias (cm):")
    for idx in IndexSensor:
        print(f"  {idx.name:9s}: {medidas.get(idx, 0.0):6.2f}")

    # Conversão em dimensões reais.
    cub = Cubagem()
    cub.altura = altura_com_ajuste(medidas.get(IndexSensor.ALTURA), cfg.ajustes)
    cub.largura = largura_com_ajuste(medidas.get(IndexSensor.FUNDO), cfg.ajustes)
    cub.comprimento = comprimento_com_ajuste(
        medidas.get(IndexSensor.ESQUERDA), medidas.get(IndexSensor.DIREITA), cfg.ajustes
    )

    fora = sensor.is_out_of_range(medidas)
    print(f"\n{cub}")
    print(f"Fora de faixa: {fora}")
    print(f"Erros: checksum={sensor.s.error_count}, timeout={sensor.s.timeout_count}")

    rs485.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
