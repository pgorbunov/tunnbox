"""One-time share links for peer configs."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_one


async def create(
    db: aiosqlite.Connection,
    *,
    peer_id: int,
    token_hash: str,
    created_by: int | None,
    expires_at: str,
    max_uses: int,
    now: str,
) -> dict[str, Any]:
    cur = await db.execute(
        """INSERT INTO share_links (peer_id, token_hash, created_by, expires_at, max_uses, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (peer_id, token_hash, created_by, expires_at, max_uses, now),
    )
    row = await fetch_one(db, "SELECT * FROM share_links WHERE id = ?", (cur.lastrowid,))
    assert row is not None
    return row


async def get_by_token_hash(db: aiosqlite.Connection, token_hash: str) -> dict[str, Any] | None:
    return await fetch_one(db, "SELECT * FROM share_links WHERE token_hash = ?", (token_hash,))


async def record_use(db: aiosqlite.Connection, link_id: int, now: str) -> None:
    await db.execute("UPDATE share_links SET uses = uses + 1, used_at = ? WHERE id = ?", (now, link_id))


async def delete_expired(db: aiosqlite.Connection, now: str) -> int:
    cur = await db.execute("DELETE FROM share_links WHERE expires_at < ? OR uses >= max_uses", (now,))
    return cur.rowcount or 0
