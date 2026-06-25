"""Login e autologout (porta de Login.java)."""

from __future__ import annotations

import logging
import time

from ..config.models import ConfigLogin

log = logging.getLogger(__name__)


class Login:
    def __init__(self, config: ConfigLogin):
        self.config = config
        self.usuario: str | None = None
        self._ultimo_uso = time.monotonic()

    def is_enabled(self) -> bool:
        return self.config.enabled

    def is_logged(self) -> bool:
        if not self.config.enabled:
            return True
        self._check_autologout()
        return self.usuario is not None

    def login(self, usuario: str, senha: str = "") -> bool:
        if self.config.usuarios and self.config.usuarios.get(usuario) not in (senha, None):
            return False
        self.usuario = usuario
        self._ultimo_uso = time.monotonic()
        log.info("Login: %s", usuario)
        return True

    def logout(self) -> None:
        log.info("Logout: %s", self.usuario)
        self.usuario = None

    def update_uso(self) -> None:
        self._ultimo_uso = time.monotonic()

    def _check_autologout(self) -> None:
        if self.usuario and self.config.minutes_autologout > 0:
            if time.monotonic() - self._ultimo_uso > self.config.minutes_autologout * 60:
                log.info("Autologout (%s)", self.usuario)
                self.usuario = None
