#!/usr/bin/env python3
"""Ferramenta de bancada: identifica e testa os periféricos por uma porta serial USB.

Serve para trabalhar SEM a placa shield (ATmega/MAX485/MAX232), usando adaptadores USB:
  - USB-RS485 (FT232RL)     -> sensores ultrassônicos (barramento RS-485)
  - USB-Serial TTL ou RS232 -> indicador de balança (Trentin / Weightech)

Nada aqui toca GPIO nem o barramento I2C: é só porta serial. Pode rodar no Raspberry
ou num PC Linux com o adaptador espetado.

USO
---
  # 1) que portas existem?
  python3 scripts/diag_serial.py --listar

  # 2) o indicador de balança fala o quê? (descobre baudrate e protocolo)
  python3 scripts/diag_serial.py --sniff /dev/ttyUSB0 --auto-baud
  python3 scripts/diag_serial.py --sniff /dev/ttyUSB0 --baud 9600 --segundos 15

  # 3) o sensor ultrassônico responde? (pelo USB-RS485)
  python3 scripts/diag_serial.py --ultra /dev/ttyUSB0 --addr 11
  python3 scripts/diag_serial.py --ultra /dev/ttyUSB0 --varrer
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Baudrates comuns em indicadores de balança e sensores industriais.
BAUDS = [9600, 19200, 38400, 57600, 115200, 4800, 2400]

# Protocolo dos ultrassônicos (mesma fórmula de cubagempi/drivers/checksum.py).
ULTRASONIC_CHECKSUM_CONST = 1234
ENDERECOS_PADRAO = [11, 13, 15, 17, 12, 14, 16, 18, 1]   # 1 = temperatura


# --------------------------------------------------------------------------- utils
def _hexdump(dados: bytes, largura: int = 16) -> str:
    linhas = []
    for i in range(0, len(dados), largura):
        pedaco = dados[i:i + largura]
        hexa = " ".join(f"{b:02X}" for b in pedaco).ljust(largura * 3 - 1)
        texto = "".join(chr(b) if 32 <= b < 127 else "." for b in pedaco)
        linhas.append(f"  {i:04X}  {hexa}  |{texto}|")
    return "\n".join(linhas)


def _abrir(porta: str, baud: int):
    import serial
    return serial.Serial(port=porta, baudrate=baud, bytesize=serial.EIGHTBITS,
                         parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0)


# --------------------------------------------------------------------------- listar
def listar() -> int:
    padroes = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/serial*", "/dev/ttyAMA*", "/dev/ttyS[0-9]"]
    achadas = []
    for p in padroes:
        achadas.extend(sorted(glob.glob(p)))
    if not achadas:
        print("Nenhuma porta serial encontrada.")
        print("Adaptador USB espetado? Rode 'lsusb' e 'dmesg | tail -20'.")
        return 1
    print("Portas seriais encontradas:\n")
    for porta in achadas:
        tipo = "adaptador USB" if porta.startswith(("/dev/ttyUSB", "/dev/ttyACM")) else "UART onboard do Pi"
        alvo = ""
        if os.path.islink(porta):
            alvo = " -> " + os.path.realpath(porta)
        print(f"  {porta:16} {tipo}{alvo}")
    print("\nDica: o adaptador USB aparece como /dev/ttyUSB0 (FT232RL/CH340).")
    print("Se aparecer só a UART onboard, o adaptador não foi reconhecido.")
    print("Rode --fixar para ver a identidade estável de cada um.")
    return 0


def fixar() -> int:
    """Mostra a identidade estável de cada adaptador + as linhas prontas p/ o config.yaml."""
    from cubagempi.hal.serial_ports import listar_portas_usb

    portas = listar_portas_usb()
    if not portas:
        print("Nenhum adaptador USB-serial conectado.")
        print("Plugue o adaptador e rode de novo ('lsusb' para conferir).")
        return 1

    print(f"{len(portas)} adaptador(es) USB-serial:\n")
    for p in portas:
        print(f"  {p.device}")
        print(f"    {p.descricao()}")
        if p.by_id:
            print(f"    fixo por SÉRIE   : {p.by_id}")
        if p.by_path:
            marca = "" if p.by_id else "   <-- use este (chip sem número de série)"
            print(f"    fixo por CONECTOR: {p.by_path}{marca}")
        if not p.by_id and not p.by_path:
            print("    *** SEM caminho estável — o udev não criou symlink.")
        print()

    print("=" * 72)
    print("COLE NO config.yaml (identidade estável, imune à ordem de enumeração):")
    print("=" * 72)
    ft = [p for p in portas if (p.produto or "").upper().find("FT232") >= 0
          or (p.by_id or "").upper().find("FT232") >= 0]
    alvo_rs485 = ft[0] if ft else portas[0]
    print("\nrs485:")
    print(f"  serial_port: {alvo_rs485.estavel}")
    print("  auto_dir: true")
    print("  baudrate: 115200")
    if len(portas) > 1:
        outros = [p for p in portas if p is not alvo_rs485]
        print("\nleitor:")
        print("  modelo: SERIAL")
        print(f"  com_port: {outros[0].estavel}")
        print("  baudrate: 9600")
    if not ft and len(portas) > 1:
        print("\n! Não identifiquei qual é o RS-485 pelo chip — confira antes de colar.")
    return 0


# --------------------------------------------------------------------------- sniff
def _detectar_protocolo(dados: bytes) -> list[str]:
    """Procura frames de balança nos bytes crus, usando os parsers reais do projeto."""
    from cubagempi.drivers.scale_protocol import Trentin, Weightech

    buf = list(dados)
    achados = []
    for nome, cls in (("Trentin", Trentin), ("Weightech", Weightech)):
        pesos = []
        for i in range(len(buf)):
            try:
                if cls.exists_peso(buf, i):
                    pesos.append(cls.parse_peso(buf, i))
            except (ValueError, IndexError):
                continue          # frame partido/ruído: só ignora
        if pesos:
            amostra = ", ".join(f"{p:g}" for p in pesos[:5])
            achados.append(f"{nome}: {len(pesos)} frame(s) válido(s) — pesos: {amostra}")
    return achados


def _ler(porta: str, baud: int, segundos: float) -> bytes:
    ser = _abrir(porta, baud)
    dados = bytearray()
    fim = time.monotonic() + segundos
    try:
        while time.monotonic() < fim:
            n = ser.in_waiting
            if n:
                dados.extend(ser.read(n))
            else:
                time.sleep(0.02)
    finally:
        ser.close()
    return bytes(dados)


def _pontuar(dados: bytes) -> float:
    """Heurística: fração de bytes ASCII imprimíveis/CR/LF. Baudrate errado => lixo."""
    if not dados:
        return 0.0
    bons = sum(1 for b in dados if 32 <= b < 127 or b in (13, 10))
    return bons / len(dados)


def sniff(porta: str, baud: int | None, segundos: float, auto: bool) -> int:
    if auto:
        print(f"Varrendo baudrates em {porta} ({segundos:g}s cada). Deixe o indicador ENVIANDO peso.\n")
        resultados = []
        for b in BAUDS:
            try:
                dados = _ler(porta, b, segundos)
            except Exception as exc:  # noqa: BLE001
                print(f"  {b:>6} bps: erro ao abrir ({exc})")
                continue
            score = _pontuar(dados)
            proto = _detectar_protocolo(dados) if dados else []
            marca = "  <-- PROTOCOLO RECONHECIDO" if proto else ""
            print(f"  {b:>6} bps: {len(dados):4d} bytes | ASCII {score*100:5.1f}%{marca}")
            for p in proto:
                print(f"           {p}")
            resultados.append((bool(proto), score, len(dados), b, dados))
        if not resultados:
            print("\nNada lido em nenhum baudrate.")
            return _dica_mudo()
        resultados.sort(reverse=True)
        achou, score, n, melhor, dados = resultados[0]
        print("\n" + "=" * 70)
        if achou:
            print(f"MELHOR PALPITE: {melhor} bps — protocolo de balança reconhecido.")
        elif n == 0:
            print("Chegou ZERO byte em todos os baudrates.")
            return _dica_mudo()
        else:
            print(f"MELHOR PALPITE: {melhor} bps (ASCII {score*100:.1f}%) — sem frame reconhecido.")
            print("Se o ASCII estiver baixo em todos, o nível elétrico pode estar errado")
            print("(RS-232 de verdade ligado num adaptador TTL, ou A/B trocados).")
        print("=" * 70)
        print("\nAmostra dos bytes:")
        print(_hexdump(dados[:160]))
        return 0

    b = baud or 9600
    print(f"Escutando {porta} @ {b} 8N1 por {segundos:g}s. Deixe o indicador ENVIANDO peso.\n")
    dados = _ler(porta, b, segundos)
    if not dados:
        print("Zero bytes recebidos.")
        return _dica_mudo()
    print(f"{len(dados)} bytes | ASCII imprimível: {_pontuar(dados)*100:.1f}%\n")
    print(_hexdump(dados[:400]))
    proto = _detectar_protocolo(dados)
    print()
    if proto:
        print("PROTOCOLO RECONHECIDO:")
        for p in proto:
            print("  " + p)
    else:
        print("Nenhum frame Trentin/Weightech reconhecido.")
        print("  - ASCII alto mas sem frame -> protocolo diferente (mande este hexdump).")
        print("  - ASCII baixo -> baudrate errado (tente --auto-baud) ou nível elétrico errado.")
    return 0


def _dica_mudo() -> int:
    print("\nNada chegou. Verifique, nesta ordem:")
    print("  1. GND em comum entre o indicador e o adaptador (o mais esquecido).")
    print("  2. TX do indicador -> RX do adaptador (não TX->TX).")
    print("  3. Nível elétrico: se a linha em repouso mede ~-12 V, é RS-232 DE VERDADE")
    print("     e o adaptador TTL (CH340G) NÃO serve — precisa de MAX3232 no meio.")
    print("  4. O indicador está configurado para transmitir (modo contínuo)?")
    return 1


# --------------------------------------------------------------------------- ultra
def _frame_ultra(addr: int, faixa: int = 1, leituras: int = 1, atraso: int = 1) -> bytes:
    data_msb = ((faixa & 0x07) << 5) + (leituras & 0x1F)
    data_lsb = atraso & 0xFF
    cs = ULTRASONIC_CHECKSUM_CONST + addr + data_msb + data_lsb
    return bytes([addr & 0xFF, data_msb & 0xFF, data_lsb & 0xFF, (cs // 256) & 0xFF, cs % 256 & 0xFF])


def _validar_rx(rx: bytes, addr_tx: int) -> str:
    if len(rx) < 5:
        return f"resposta curta ({len(rx)} bytes, esperado 5)"
    a, msb, lsb, cmsb, clsb = rx[0], rx[1], rx[2], rx[3], rx[4]
    cs_calc = ULTRASONIC_CHECKSUM_CONST + a + msb + lsb
    cs_rx = cmsb * 256 + clsb
    if cs_calc != cs_rx:
        return f"CHECKSUM INVÁLIDO (calculado {cs_calc}, recebido {cs_rx})"
    if a != addr_tx:
        return f"endereço ecoado {a} != enviado {addr_tx}"
    return f"OK — endereço {a}, dado = {msb * 256 + lsb}"


def _consultar(ser, addr: int, timeout_ms: int) -> bytes:
    tx = _frame_ultra(addr)
    ser.reset_input_buffer()
    ser.write(tx)
    ser.flush()
    buf = bytearray()
    fim = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < fim and len(buf) < 5:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        else:
            time.sleep(0.001)
    return bytes(buf)


def ultra(porta: str, addr: int, baud: int, varrer: bool, timeout_ms: int) -> int:
    print(f"Barramento RS-485 em {porta} @ {baud} 8N1 (adaptador USB = auto-direção, sem DE)\n")
    ser = _abrir(porta, baud)
    try:
        alvos = ENDERECOS_PADRAO if varrer else [addr]
        respondeu = 0
        for a in alvos:
            tx = _frame_ultra(a)
            rx = _consultar(ser, a, timeout_ms)
            tx_s = " ".join(f"{b:02X}" for b in tx)
            if not rx:
                print(f"  addr {a:>3}: TX [{tx_s}] -> sem resposta")
                continue
            rx_s = " ".join(f"{b:02X}" for b in rx)
            print(f"  addr {a:>3}: TX [{tx_s}] -> RX [{rx_s}]  {_validar_rx(rx, a)}")
            respondeu += 1
            time.sleep(0.01)
    finally:
        ser.close()

    print()
    if respondeu:
        print(f"{respondeu} sensor(es) responderam. O barramento RS-485 está funcionando pelo USB.")
        return 0
    print("Ninguém respondeu. Verifique:")
    print("  1. A e B trocados? (é o erro mais comum — inverta e teste de novo)")
    print("  2. GND comum entre o adaptador e os sensores.")
    print("  3. Os sensores estão ALIMENTADOS (5 V) e o GND é o mesmo do adaptador?")
    print("  4. Terminação 120 Ω só no fim da linha.")
    print("  5. Endereço certo? Tente --varrer para testar todos os padrão.")
    return 1


# --------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Diagnóstico de bancada dos periféricos por serial USB (sem o shield).",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--listar", action="store_true", help="lista as portas seriais disponíveis")
    ap.add_argument("--fixar", action="store_true",
                    help="mostra a identidade estável de cada adaptador + linhas p/ o config.yaml")
    ap.add_argument("--sniff", metavar="PORTA", help="escuta a porta e identifica o protocolo da balança")
    ap.add_argument("--ultra", metavar="PORTA", help="consulta sensor ultrassônico via RS-485")
    ap.add_argument("--baud", type=int, help="baudrate (balança: 9600 | ultrassônico: 115200)")
    ap.add_argument("--auto-baud", action="store_true", help="varre os baudrates comuns (use com --sniff)")
    ap.add_argument("--segundos", type=float, default=8.0, help="tempo de escuta por baudrate (default 8)")
    ap.add_argument("--addr", type=int, default=11, help="endereço do sensor (default 11)")
    ap.add_argument("--varrer", action="store_true", help="testa todos os endereços padrão (use com --ultra)")
    ap.add_argument("--timeout-ms", type=int, default=50, help="timeout de resposta do sensor (default 50)")
    args = ap.parse_args(argv)

    try:
        import serial  # noqa: F401
    except ImportError:
        print("pyserial não instalado. Rode: pip3 install pyserial --break-system-packages")
        return 1

    if args.listar:
        return listar()
    if args.fixar:
        return fixar()
    if args.sniff:
        return sniff(args.sniff, args.baud, args.segundos, args.auto_baud)
    if args.ultra:
        return ultra(args.ultra, args.addr, args.baud or 115200, args.varrer, args.timeout_ms)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
