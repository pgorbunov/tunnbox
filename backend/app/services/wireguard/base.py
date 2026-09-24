"""WireGuardBackend protocol and the dump data shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class PeerDump:
    public_key: str
    preshared: bool
    endpoint: str | None
    allowed_ips: str
    latest_handshake: datetime | None
    rx: int
    tx: int
    keepalive: int


@dataclass
class InterfaceDump:
    listen_port: int
    public_key: str
    peers: list[PeerDump] = field(default_factory=list)


class WireGuardBackend(Protocol):
    """Operations on live WireGuard interfaces; config files are rendered elsewhere."""

    mode: str

    async def is_active(self, name: str) -> bool: ...

    async def up(self, name: str) -> None: ...

    async def down(self, name: str) -> None: ...

    async def sync(self, name: str) -> None: ...

    async def dump(self, name: str) -> InterfaceDump: ...

    async def version(self) -> str | None: ...

    async def kernel_module(self) -> bool: ...
