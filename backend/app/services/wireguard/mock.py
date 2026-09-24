"""Mock backend: in-memory active set plus lively simulated stats.

`dump()` reads the rendered `.conf` to learn the peers, then produces
deterministic-but-growing counters seeded by each peer's public key so the UI
looks real without WireGuard. About 60 % of peers are online at any moment and
each peer flips state on its own slow cadence.
"""

from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas.common import validate_interface_name
from app.services.wireguard.base import InterfaceDump, PeerDump
from app.services.wireguard.renderer import parse_config


def _seed(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


class _PeerSim:
    """Counters and handshake state for one simulated peer."""

    def __init__(self, public_key: str) -> None:
        self.public_key = public_key
        base = random.Random(_seed(public_key))
        self.rx = base.randint(5_000_000, 900_000_000)
        self.tx = base.randint(1_000_000, 300_000_000)
        self.rx_rate = base.uniform(2_000, 400_000)  # bytes/sec while online
        self.tx_rate = base.uniform(500, 120_000)
        self.online_bias = base.random()
        self.endpoint = f"{base.randint(20, 220)}.{base.randint(0, 255)}.{base.randint(0, 255)}.{base.randint(1, 254)}:{base.randint(1024, 65000)}"
        self.last_tick = time.time()
        self.last_handshake: datetime | None = None
        self.was_online = False

    def online(self, now: float) -> bool:
        # Re-roll roughly every 8 minutes per peer, offset by key so peers don't flip together.
        epoch = int((now + _seed(self.public_key) % 480) // 480)
        roll = random.Random(_seed(self.public_key, epoch)).random()
        return roll < 0.60 + (self.online_bias - 0.5) * 0.2

    def tick(self, now: float) -> PeerDump:
        elapsed = max(0.0, min(now - self.last_tick, 3600.0))
        self.last_tick = now
        is_online = self.online(now)
        rng = random.Random(_seed(self.public_key, int(now)))
        if is_online:
            self.rx += int(elapsed * self.rx_rate * rng.uniform(0.2, 1.8))
            self.tx += int(elapsed * self.tx_rate * rng.uniform(0.2, 1.8))
            self.last_handshake = datetime.now(timezone.utc) - timedelta(seconds=rng.randint(1, 110))
        elif self.was_online and self.last_handshake is None:
            self.last_handshake = datetime.now(timezone.utc) - timedelta(minutes=rng.randint(5, 600))
        self.was_online = is_online
        return PeerDump(
            public_key=self.public_key,
            preshared=True,
            endpoint=self.endpoint if self.last_handshake else None,
            allowed_ips="",
            latest_handshake=self.last_handshake,
            rx=self.rx,
            tx=self.tx,
            keepalive=25,
        )


class MockBackend:
    mode = "mock"

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.active: set[str] = set()
        self._peers: dict[str, _PeerSim] = {}

    async def is_active(self, name: str) -> bool:
        validate_interface_name(name)
        return name in self.active

    async def up(self, name: str) -> None:
        validate_interface_name(name)
        self.active.add(name)

    async def down(self, name: str) -> None:
        validate_interface_name(name)
        self.active.discard(name)

    async def sync(self, name: str) -> None:
        validate_interface_name(name)

    async def dump(self, name: str) -> InterfaceDump:
        validate_interface_name(name)
        path = self.config_dir / f"{name}.conf"
        if not path.is_file():
            return InterfaceDump(listen_port=0, public_key="")
        parsed = parse_config(path.read_text(encoding="utf-8"))
        iface = parsed["interface"]
        port = int(iface.get("listenport") or 0)
        dump = InterfaceDump(listen_port=port, public_key="")
        now = time.time()
        for peer in parsed["peers"]:
            key = peer.get("publickey")
            if not key:
                continue
            sim = self._peers.get(key)
            if sim is None:
                sim = self._peers[key] = _PeerSim(key)
            entry = sim.tick(now)
            entry.allowed_ips = peer.get("allowedips", "")
            entry.preshared = bool(peer.get("presharedkey"))
            entry.keepalive = int(peer.get("persistentkeepalive") or 0)
            dump.peers.append(entry)
        return dump

    async def version(self) -> str | None:
        return None

    async def kernel_module(self) -> bool:
        return False
