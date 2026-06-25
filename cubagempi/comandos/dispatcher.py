"""Dispatcher de comandos operacionais (porta de EtiquetaCommandFactory/ControllerCommon).

O operador digita um comando no campo de etiqueta (ex.: *r* reinicia, *ip* mostra o IP).
Cobre os comandos do bloco <command> do config.xml. Comandos não reconhecidos retornam None.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)

Handler = Callable[[str], str]


@dataclass
class Command:
    nome: str
    pattern: str
    handler: Handler
    prefixo: bool = False


class CommandDispatcher:
    def __init__(self) -> None:
        self._commands: list[Command] = []

    def register(self, nome: str, pattern: str, handler: Handler, prefixo: bool = False) -> None:
        if pattern:
            self._commands.append(Command(nome, pattern.strip().lower(), handler, prefixo))

    def _match(self, text: str) -> Optional[Command]:
        t = text.strip().lower()
        for cmd in self._commands:
            if cmd.prefixo and t.startswith(cmd.pattern):
                return cmd
            if not cmd.prefixo and t == cmd.pattern:
                return cmd
        return None

    def is_command(self, text: str) -> bool:
        return self._match(text) is not None

    def execute(self, text: str) -> Optional[str]:
        cmd = self._match(text)
        if cmd is None:
            return None
        log.info("Executando comando: %s (%s)", cmd.nome, text)
        try:
            return cmd.handler(text)
        except Exception as exc:  # noqa: BLE001
            log.exception("Erro no comando %s", cmd.nome)
            return f"Erro no comando {cmd.nome}: {exc}"


# ----------------------------------------------------------------- helpers
def _get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return socket.gethostbyname(socket.gethostname())


def _reiniciar(_: str) -> str:
    if sys.platform.startswith("linux"):
        subprocess.Popen(["sudo", "reboot"])
        return "Reiniciando..."
    return "Reiniciar: disponível apenas no Linux/Raspberry Pi"


def _desligar(_: str) -> str:
    if sys.platform.startswith("linux"):
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return "Desligando..."
    return "Desligar: disponível apenas no Linux/Raspberry Pi"


def build_default_dispatcher(app) -> CommandDispatcher:
    """Monta o dispatcher com TODOS os comandos do config.xml, ligados ao App."""
    d = CommandDispatcher()

    # ações de sistema
    d.register("ip", "*ip*", lambda _: f"IP: {_get_ip()}")
    d.register("reiniciar", "*r*", _reiniciar)
    d.register("desligar", "*d*", _desligar)
    d.register("rede", "*rede*", lambda _: app.info_rede())

    # calibração pelo cubo de aferição
    d.register("calibrar_cubo", "*cal*", lambda _: app.calibrar_com_cubo())

    # balança / medição
    d.register("tara", "*tara*", lambda _: app.tarar())
    d.register("envelope", "*e*", lambda _: app.toggle_envelope())
    d.register("executar_camera", "*camera*", lambda _: app.executar_camera())

    # integração
    d.register("alternar_integracao", "*i*", lambda _: app.alternar_integracao())
    d.register("reexecutar_integracao", "*integracao*", lambda _: app.reexecutar_integracao())
    d.register("limpar_fila", "*fila*", lambda _: app.limpar_fila())

    # banco / dados
    d.register("limpar_banco", "*limpar*", lambda _: app.limpar_banco())
    d.register("totalizacao", "*total*", lambda _: app.reset_totalizacao())

    # sessão / config
    d.register("logout", "*logout*", lambda _: app.logout())
    d.register("config", "*config*", lambda _: app.resumo_config())
    d.register("especificacao", "*spec*", lambda _: app.especificacao())
    d.register("bordas", "*bordas*", lambda _: app.toggle_bordas())
    d.register("debug", "*debug*", lambda _: app.toggle_debug())

    # modos de etiqueta
    d.register("cep", "*cep*", lambda _: app.toggle_cep())
    d.register("danfe", "*danfe*", lambda _: app.toggle_danfe())

    # OTA / nuvem (implementação completa na fase de deploy)
    d.register("atualizar", "*atualizar*", lambda _: app.atualizar() if hasattr(app, "atualizar")
               else "Atualização OTA: configurar na fase de deploy")
    d.register("download", "*download*", lambda _: app.download_config() if hasattr(app, "download_config")
               else "Download de config: configurar na fase de deploy")

    # informativos / fiscais
    d.register("manual", "*manual*", lambda _: "Manual: http://<ip-do-equipamento>:%d" % app.config.web.porta)
    d.register("plp", "*plp*", lambda _: "PLP: recurso fiscal (configurar conforme transportadora)")
    d.register("quantidade", "*qtd*", lambda _: "Quantidade: escaneie 'NOTA+N' no modo nota+volumes")

    # sorter (prefixo *485)
    d.register("enviar_sorter", "*485", lambda t: app.enviar_sorter(t) if hasattr(app, "enviar_sorter")
               else "Sorter: disponível nos modelos com classificador", prefixo=True)

    return d
