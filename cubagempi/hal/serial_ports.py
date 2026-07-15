"""Identidade estável das portas seriais USB — a "fixação" das portas.

PROBLEMA
--------
`/dev/ttyUSB0` é atribuído por ORDEM DE ENUMERAÇÃO do kernel. Com dois adaptadores
plugados (ex.: USB-RS485 dos sensores + leitor de código de barras), eles TROCAM de
nome entre um boot e outro — e o equipamento passa a falar no dispositivo errado sem
nenhum aviso. Pior: `leitor.com_port` e `rs485.serial_port` têm o MESMO default
(/dev/ttyUSB0), então os dois disputam a mesma porta.

SOLUÇÃO
-------
Referenciar a porta por uma identidade estável, resolvida a cada boot (fixação).

Ordem de preferência da identidade:
1. `/dev/serial/by-id/...`   — deriva do número de série do chip. O FT232RL TEM
                               número de série; o CH340 normalmente NÃO tem.
2. `/dev/serial/by-path/...` — deriva da posição física do conector USB. Cobre os
                               chips sem número de série, mas muda se você trocar
                               o cabo de conector.

Formas aceitas em `rs485.serial_port` e `leitor.com_port`:

    /dev/ttyUSB0                                 nó cru — funciona, mas NÃO é estável
    /dev/serial/by-id/usb-FTDI_FT232R_...        estável (recomendado)
    /dev/serial/by-path/platform-...-port0       estável por conector
    FT232R                                       fragmento — procura em by-id/produto
    A50285BI                                     fragmento — número de série

Um fragmento que casa com mais de um adaptador é ERRO (ambíguo), nunca um chute.
"""

from __future__ import annotations

import glob
import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)

_PREFIXOS_USB = ("/dev/ttyUSB", "/dev/ttyACM")


class PortaNaoEncontrada(FileNotFoundError):
    """A porta pedida não existe (adaptador desligado ou identidade errada)."""


class PortaAmbigua(RuntimeError):
    """O fragmento casou com mais de um adaptador — não dá para adivinhar qual."""


@dataclass
class PortaUsb:
    device: str
    by_id: str | None = None
    by_path: str | None = None
    vid: int | None = None
    pid: int | None = None
    serie: str | None = None
    produto: str | None = None
    fabricante: str | None = None

    @property
    def estavel(self) -> str:
        """Melhor caminho estável disponível: by-id > by-path > nó cru."""
        return self.by_id or self.by_path or self.device

    def descricao(self) -> str:
        d = " ".join(p for p in (self.fabricante, self.produto) if p) or "?"
        if self.vid is not None and self.pid is not None:
            d += f" [{self.vid:04x}:{self.pid:04x}]"
        if self.serie:
            d += f" série={self.serie}"
        return d

    def _texto_busca(self) -> str:
        return " ".join(filter(None, (self.by_id, self.by_path, self.serie,
                                      self.produto, self.fabricante, self.device))).lower()


def _links(sub: str) -> dict[str, str]:
    """Mapa {caminho_real: link} de /dev/serial/<sub>/ (symlinks criados pelo udev)."""
    out: dict[str, str] = {}
    base = f"/dev/serial/{sub}"
    if not os.path.isdir(base):
        return out
    for nome in os.listdir(base):
        link = os.path.join(base, nome)
        try:
            out[os.path.realpath(link)] = link
        except OSError:
            continue
    return out


def listar_portas_usb() -> list[PortaUsb]:
    """Lista os adaptadores USB-serial presentes, com sua identidade estável."""
    by_id, by_path = _links("by-id"), _links("by-path")
    portas: list[PortaUsb] = []
    vistos: set[str] = set()

    try:
        from serial.tools import list_ports
        infos = list(list_ports.comports())
    except Exception:  # noqa: BLE001 - sem pyserial/tools: cai para o glob abaixo
        infos = []

    for i in infos:
        if not i.device.startswith(_PREFIXOS_USB):
            continue
        real = os.path.realpath(i.device)
        vistos.add(real)
        portas.append(PortaUsb(i.device, by_id.get(real), by_path.get(real),
                               i.vid, i.pid, i.serial_number, i.product, i.manufacturer))

    # Dispositivos que o pyserial não enxergou (ou pyserial ausente).
    for pref in _PREFIXOS_USB:
        for dev in sorted(glob.glob(pref + "*")):
            real = os.path.realpath(dev)
            if real not in vistos:
                vistos.add(real)
                portas.append(PortaUsb(dev, by_id.get(real), by_path.get(real)))

    return sorted(portas, key=lambda p: p.device)


def e_usb(porta: str) -> bool:
    return bool(porta) and porta.startswith(_PREFIXOS_USB)


def e_identidade_usb(pedida: str) -> bool:
    """True se `pedida` deve ser resolvida por este módulo (USB, link estável ou fragmento)."""
    if not pedida:
        return False
    if pedida.startswith("/dev/serial/"):
        return True
    if e_usb(pedida):
        return True
    return not pedida.startswith("/dev/")      # qualquer coisa sem /dev/ é fragmento


def resolver_porta(pedida: str) -> tuple[str, PortaUsb | None]:
    """Resolve `pedida` para (device_real, PortaUsb|None).

    Levanta PortaNaoEncontrada / PortaAmbigua — nunca devolve um palpite.
    """
    portas = listar_portas_usb()

    if pedida.startswith("/dev/"):
        if not os.path.exists(pedida):
            disp = ", ".join(p.device for p in portas) or "nenhum adaptador USB conectado"
            raise PortaNaoEncontrada(
                f"Porta {pedida} não existe. Presentes: {disp}. "
                f"Confira 'ls -l /dev/serial/by-id/'."
            )
        real = os.path.realpath(pedida)
        for p in portas:
            if os.path.realpath(p.device) == real:
                return real, p
        return real, None

    alvo = pedida.strip().lower()
    achadas = [p for p in portas if alvo in p._texto_busca()]
    if not achadas:
        disp = "; ".join(f"{p.device} ({p.descricao()})" for p in portas) or "nenhum"
        raise PortaNaoEncontrada(
            f"Nenhum adaptador USB-serial casa com '{pedida}'. Presentes: {disp}."
        )
    if len(achadas) > 1:
        quais = "; ".join(f"{p.device} -> {p.estavel}" for p in achadas)
        raise PortaAmbigua(
            f"'{pedida}' casa com {len(achadas)} adaptadores: {quais}. "
            f"Use a identidade completa (by-id) para desambiguar."
        )
    p = achadas[0]
    return os.path.realpath(p.device), p


def log_fixacao() -> list[PortaUsb]:
    """Loga a fixação das portas USB. Chamado a cada boot (ver app/main.py)."""
    portas = listar_portas_usb()
    if not portas:
        log.info("Fixação de portas: nenhum adaptador USB-serial presente.")
        return portas

    log.info("Fixação de portas USB-serial — %d adaptador(es):", len(portas))
    for p in portas:
        if p.by_id:
            log.info("  %-13s fixo por SÉRIE  -> %s | %s", p.device, p.by_id, p.descricao())
        elif p.by_path:
            log.info("  %-13s fixo por CONECTOR -> %s | %s  (chip sem número de série; "
                     "trocar de porta USB muda este caminho)", p.device, p.by_path, p.descricao())
        else:
            log.warning("  %-13s SEM caminho estável | %s  (udev não criou symlink; "
                        "o nome pode trocar a cada boot)", p.device, p.descricao())
    return portas


def aviso_se_instavel(rotulo: str, pedida: str, porta: PortaUsb | None) -> None:
    """Se a config aponta para um nó cru (/dev/ttyUSB0), diz exatamente como fixar."""
    if not e_usb(pedida) or porta is None:
        return
    if porta.estavel == porta.device:
        log.warning("%s está em %s e o udev não deu caminho estável — o nome pode trocar no "
                    "próximo boot.", rotulo, pedida)
        return
    log.warning("%s está usando o nó cru %s, que NÃO é estável (troca de nome se outro "
                "adaptador for plugado). Fixe assim na config:  %s", rotulo, pedida, porta.estavel)
