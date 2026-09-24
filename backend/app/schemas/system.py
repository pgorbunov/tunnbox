"""System schemas."""

from __future__ import annotations

from typing import Literal

from app.schemas.common import ApiModel


class Health(ApiModel):
    status: Literal["ok"] = "ok"


class SystemInfo(ApiModel):
    version: str
    backend_mode: Literal["real", "mock"]
    wireguard_version: str | None
    kernel_module: bool
    python_version: str
    os: str
    uptime_seconds: int
    database_size_bytes: int
    config_path: str
    hostname: str
