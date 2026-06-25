"""Comandos operacionais digitados no campo de etiqueta (*tara*, *r*, *ip*, ...)."""

from .dispatcher import CommandDispatcher, build_default_dispatcher

__all__ = ["CommandDispatcher", "build_default_dispatcher"]
