"""WireGuard backends (real via wg/wg-quick, or an in-memory mock)."""

from __future__ import annotations

from pathlib import Path

from app.services.wireguard.base import WireGuardBackend
from app.services.wireguard.mock import MockBackend
from app.services.wireguard.real import RealBackend


def get_backend(mode: str, config_dir: Path) -> WireGuardBackend:
    """Build the backend for a resolved mode (`real` or `mock`)."""
    if mode == "real":
        return RealBackend(config_dir)
    return MockBackend(config_dir)


__all__ = ["WireGuardBackend", "MockBackend", "RealBackend", "get_backend"]
