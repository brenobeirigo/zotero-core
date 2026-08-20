"""Backends: where a library snapshot comes from, and who does the writing."""

from __future__ import annotations

from ..errors import BackendUnavailable
from .base import Backend
from .null import NullBackend

__all__ = ["Backend", "NullBackend", "get_backend"]

#: Names accepted by :func:`get_backend`.
BACKENDS = ("null", "web", "desktop")


def get_backend(name: str, **kwargs):
    """Construct a backend by name, with a useful error when one is missing.

    Imports are deferred so that ``import zotero_core`` works with no optional
    dependency installed, on any platform.
    """
    if name == "null":
        return NullBackend()
    if name == "web":
        from .web import WebApiBackend

        return WebApiBackend(**kwargs)
    if name == "desktop":
        from .desktop import DesktopBridgeBackend

        return DesktopBridgeBackend(**kwargs)
    raise BackendUnavailable(f"Unknown backend {name!r}; expected one of {', '.join(BACKENDS)}")
