"""Ponto de entrada principal: monta o App e sobe interfaces (web + GUI)."""

from __future__ import annotations

import argparse
import logging
import signal
import threading

from ..config import load_config
from ..core import setup_logging
from .app import App

log = logging.getLogger(__name__)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cubagem PI (Python)")
    p.add_argument("--config", help="caminho do config.yaml")
    p.add_argument("--real", action="store_true", help="usa hardware real (Raspberry Pi)")
    p.add_argument("--no-web", action="store_true", help="não inicia o painel web")
    p.add_argument("--no-gui", action="store_true", help="modo headless (sem janela)")
    p.add_argument("--kiosk", action="store_true", help="GUI em tela cheia (operação no equipamento)")
    p.add_argument("--db", default="cubagem.db", help="arquivo do banco SQLite")
    p.add_argument("--debug", action="store_true", help="log em nível DEBUG")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    from .. import __version__ as _versao
    from ..boot_trace import iniciar_boot, marco, passo
    iniciar_boot(_versao, "REAL (hardware)" if args.real else "SIMULADO")

    with passo("1", "Carregando configuracao (config.yaml)"):
        cfg = load_config(args.config)

    # Fixacao das portas USB-serial: /dev/ttyUSB0 e atribuido por ordem de enumeracao,
    # entao RS-485 e leitor trocam de nome entre boots. Logamos a identidade estavel de
    # cada adaptador a cada boot — e dizemos como fixar quando a config usa um no cru.
    with passo("1.5", "Fixando portas seriais USB (identidade estavel)"):
        from ..hal.serial_ports import log_fixacao
        log_fixacao()

    with passo("2", "Montando aplicacao + hardware "
                    "(balanca, RS-485, I2C, ATmega, sensores, LED)"):
        app = App(cfg, simulado=not args.real, db_path=args.db, config_path=args.config)

    with passo("3", "Iniciando servicos internos (workers, perifericos, agente de frota)"):
        app.start()

    web = None
    if not args.no_web:
        with passo("4", f"Subindo servidor web na porta {cfg.web.porta}"):
            from ..web import WebServer
            web = WebServer(app, cfg.web.porta)
            web.start()

    marco(f"PASSO 5 OK        | PRONTO -- backend no ar (tela em http://localhost:{cfg.web.porta})")

    if args.no_gui:
        log.info("Modo headless. Ctrl+C para sair.")
        parar = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: parar.set())
        signal.signal(signal.SIGTERM, lambda *_: parar.set())
        parar.wait()
    else:
        try:
            from ..gui import GuiApp
            GuiApp(app, kiosk=args.kiosk).run()
        except Exception as exc:  # noqa: BLE001 - sem display? cai p/ headless
            log.warning("GUI indisponível (%s); rodando headless. Ctrl+C para sair.", exc)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass

    log.info("Encerrando...")
    if web:
        web.stop()
    app.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
