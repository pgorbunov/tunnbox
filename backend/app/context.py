"""Per-application context shared by services and API dependencies."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.core.crypto import SecretBox
from app.core.ratelimit import RateLimiter
from app.core.scheduler import Scheduler
from app.services.wireguard.base import WireGuardBackend


@dataclass
class LiveCache:
    """Volatile per-process state fed by the stats sampler."""

    endpoints: dict[int, str | None] = field(default_factory=dict)  # peer_id -> endpoint
    raw_counters: dict[int, tuple[int, int]] = field(default_factory=dict)  # peer_id -> last raw (rx, tx)
    last_sample_ts: dict[int, float] = field(default_factory=dict)  # peer_id -> monotonic ts
    last_online: dict[int, bool] = field(default_factory=dict)


@dataclass
class AppContext:
    settings: Settings
    backend: WireGuardBackend
    secrets: SecretBox
    limiter: RateLimiter = field(default_factory=RateLimiter)
    scheduler: Scheduler = field(default_factory=Scheduler)
    live: LiveCache = field(default_factory=LiveCache)
    started_at: float = field(default_factory=time.monotonic)

    @property
    def db_path(self) -> Path:
        return self.settings.db_path
