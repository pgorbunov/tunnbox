"""API keys (hashed at rest)."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one


def _decode(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    row["scopes"] = json.loads(row["scopes"] or "[]")
    return row


async def create(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    name: str,
    prefix: str,
    key_hash: str,
    scopes: list[str],
    expires_at: str | None,
    now: str,
) -> dict[str, Any]:
    cur = await db.execute(
        """INSERT INTO api_keys (user_id, name, prefix, key_hash, scopes, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, prefix, key_hash, json.dumps(scopes), expires_at, now),
    )
    key = await get(db, int(cur.lastrowid or 0))
    assert key is not None
    return key


async def get(db: aiosqlite.Connection, key_id: int) -> dict[str, Any] | None:
    return _decode(await fetch_one(db, "SELECT * FROM api_keys WHERE id = ?", (key_id,)))


async def get_by_hash(db: aiosqlite.Connection, key_hash: str) -> dict[str, Any] | None:
    return _decode(await fetch_one(db, "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)))


async def list_for_user(db: aiosqlite.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = await fetch_all(db, "SELECT * FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,))
    return [_decode(r) for r in rows if r]  # type: ignore[misc]


async def list_all(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    rows = await fetch_all(db, "SELECT * FROM api_keys ORDER BY id DESC")
    return [_decode(r) for r in rows if r]  # type: ignore[misc]


async def touch(db: aiosqlite.Connection, key_id: int, now: str) -> None:
    await db.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, key_id))


async def revoke(db: aiosqlite.Connection, key_id: int, now: str) -> None:
    await db.execute("UPDATE api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (now, key_id))


async def revoke_all_for_user(db: aiosqlite.Connection, user_id: int, now: str) -> None:
    await db.execute("UPDATE api_keys SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id))
