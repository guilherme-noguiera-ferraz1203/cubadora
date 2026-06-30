"""Rastreador de passos da inicializacao (boot) do equipamento.

Objetivo: diagnosticar EM QUE PONTO o equipamento trava ou reinicia durante a
subida — tipicamente um brownout de energia durante a inicializacao do hardware
real (RS-485, I2C, ATmega, balanca). Cada passo e gravado em TRES lugares:

  1. arquivo persistente  -> data/boot-passos.log   (sobrevive a queda de energia)
  2. stdout               -> journalctl -u cubagempi / execucao em primeiro plano
  3. log do Python        -> log normal da aplicacao

Como LER no equipamento:
    cat ~/cubagem-pi/python/data/boot-passos.log      # ve o ultimo passo alcancado
    tail -f ~/cubagem-pi/python/data/boot-passos.log   # ao vivo
    journalctl -u cubagempi -f                         # ao vivo (servico)

Como INTERPRETAR a ultima linha do arquivo:
    "PASSO X OK"            -> o passo terminou bem.
    "PASSO X FALHOU: ..."   -> o passo deu erro de software (Python) -> e a causa.
    "PASSO X INICIANDO"     -> (sem OK/FALHOU depois) o equipamento MORREU durante
                               esse passo: desligou/reiniciou no meio. Forte indicio
                               de QUEDA DE ENERGIA (brownout) no hardware desse passo.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager

log = logging.getLogger(__name__)

# Caminho do arquivo de passos (relativo ao WorkingDirectory do servico = .../python).
_ARQUIVO = os.environ.get("CUBAGEM_BOOT_LOG", "data/boot-passos.log")
# Se o arquivo passar disso (loop de boot acumulando), zera no proximo boot.
_MAX_BYTES = 200_000


def _escrever(linha: str) -> None:
    # 1) stdout (journal / primeiro plano)
    try:
        sys.stdout.write(linha + "\n")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass
    # 2) arquivo persistente (flush + fsync para sobreviver a corte de energia)
    try:
        pasta = os.path.dirname(_ARQUIVO)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(_ARQUIVO, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:  # noqa: BLE001
        pass


def iniciar_boot(versao: str, modo: str) -> None:
    """Marca o inicio de uma tentativa de boot no arquivo de passos."""
    try:
        if os.path.exists(_ARQUIVO) and os.path.getsize(_ARQUIVO) > _MAX_BYTES:
            os.remove(_ARQUIVO)
    except Exception:  # noqa: BLE001
        pass
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    _escrever("")
    _escrever("=" * 64)
    _escrever(f"===== BOOT {ts}   versao {versao}   modo {modo} =====")
    _escrever("=" * 64)


def marco(texto: str) -> None:
    """Linha solta de progresso (sem inicio/fim), p.ex. 'PRONTO'."""
    ts = time.strftime("%H:%M:%S")
    _escrever(f"{ts} | {texto}")
    log.info("boot: %s", texto)


@contextmanager
def passo(numero: str, descricao: str):
    """Envolve um passo da inicializacao. Grava INICIANDO antes e OK/FALHOU depois.

    Se o processo morrer (corte de energia/reset) no meio do bloco, o arquivo fica
    com 'PASSO X INICIANDO' como ultima linha — apontando exatamente onde parou.
    """
    ts = time.strftime("%H:%M:%S")
    _escrever(f"{ts} | PASSO {numero} INICIANDO | {descricao}")
    log.info("PASSO %s iniciando: %s", numero, descricao)
    t0 = time.monotonic()
    try:
        yield
    except BaseException as exc:  # noqa: BLE001 - registra ate SystemExit/KeyboardInterrupt
        dt = time.monotonic() - t0
        _escrever(f"{ts} | PASSO {numero} FALHOU    | {descricao} -> "
                  f"{type(exc).__name__}: {exc}  ({dt:.2f}s)")
        log.exception("PASSO %s FALHOU: %s", numero, descricao)
        raise
    else:
        dt = time.monotonic() - t0
        _escrever(f"{ts} | PASSO {numero} OK        | {descricao}  ({dt:.2f}s)")
