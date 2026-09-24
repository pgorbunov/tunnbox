"""Runtime-editable settings stored as strings."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all

INT_KEYS = {"default_mtu", "default_keepalive", "audit_retention_days", "stats_retention_days", "ui_refresh_seconds"}
NULLABLE_KEYS = {"default_mtu"}
KEYS = (
    "public_endpoint", "default_dns", "default_mtu", "default_keepalive", "default_client_allowed_ips",
    "audit_retention_days", "stats_retention_days", "ui_refresh_seconds",
)


def defaults(*, public_endpoint: str, default_dns: str, stats_retention_days: int) -> dict[str, Any]:
    return {
        "public_endpoint": public_endpoint,
        "default_dns": default_dns,
        "default_mtu": None,
        "default_keepalive": 25,
        "default_client_allowed_ips": "0.0.0.0/0, ::/0",
        "audit_retention_days": 90,
        "stats_retention_days": stats_retention_days,
        "ui_refresh_seconds": 10,
    }


def _to_str(value: Any) -> str:
    return "" if value is None else str(value)


def _from_str(key: str, raw: str) -> Any:
    if key in INT_KEYS:
        if raw == "":
            return None if key in NULLABLE_KEYS else 0
        try:
            return int(raw)
        except ValueError:
            return None if key in NULLABLE_KEYS else 0
    return raw


async def ensure_defaults(db: aiosqlite.Connection, values: dict[str, Any], now: str) -> None:
    for key, value in values.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (key, _to_str(value), now)
        )


async def get_all(db: aiosqlite.Connection) -> dict[str, Any]:
    rows = await fetch_all(db, "SELECT key, value FROM settings")
    raw = {r["key"]: r["value"] for r in rows}
    return {key: _from_str(key, raw.get(key, "")) for key in KEYS}


async def set_many(db: aiosqlite.Connection, values: dict[str, Any], now: str) -> None:
    for key, value in values.items():
        if key not in KEYS:
            continue
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, _to_str(value), now),
        )
