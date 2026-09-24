"""Server-side login sessions (refresh-token backed)."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one


async def create(
    db: aiosqlite.Connection,
    *,
    session_id: str,
    user_id: int,
    refresh_hash: str,
    ip: str | None,
    user_agent: str | None,
    now: str,
    expires_at: str,
    absolute_expires_at: str,
) -> None:
    await db.execute(
        """INSERT INTO sessions (id, user_id, refresh_hash, ip, user_agent, created_at, last_used_at,
                                 expires_at, absolute_expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, user_id, refresh_hash, ip, user_agent, now, now, expires_at, absolute_expires_at),
    )


async def get(db: aiosqlite.Connection, session_id: str) -> dict[str, Any] | None:
    return await fetch_one(db, "SELECT * FROM sessions WHERE id = ?", (session_id,))


async def get_by_refresh_hash(db: aiosqlite.Connection, refresh_hash: str) -> dict[str, Any] | None:
    return await fetch_one(db, "SELECT * FROM sessions WHERE refresh_hash = ?", (refresh_hash,))


async def rotate(
    db: aiosqlite.Connection, session_id: str, old_hash: str, refresh_hash: str, now: str, expires_at: str
) -> bool:
    """Swap in a new refresh hash only if `old_hash` is still current; remember the old one.

    Returns False when the token was already rotated (concurrent or replayed refresh).
    """
    cur = await db.execute(
        "UPDATE sessions SET refresh_hash = ?, last_used_at = ?, expires_at = ? "
        "WHERE id = ? AND refresh_hash = ? AND revoked_at IS NULL",
        (refresh_hash, now, expires_at, session_id, old_hash),
    )
    if (cur.rowcount or 0) != 1:
        return False
    await db.execute(
        "INSERT OR REPLACE INTO refresh_token_history (refresh_hash, session_id, rotated_at) VALUES (?, ?, ?)",
        (old_hash, session_id, now),
    )
    return True


async def session_id_for_rotated_hash(db: aiosqlite.Connection, refresh_hash: str) -> str | None:
    row = await fetch_one(db, "SELECT session_id FROM refresh_token_history WHERE refresh_hash = ?", (refresh_hash,))
    return row["session_id"] if row else None


async def touch(db: aiosqlite.Connection, session_id: str, now: str) -> None:
    await db.execute("UPDATE sessions SET last_used_at = ? WHERE id = ?", (now, session_id))


async def revoke(db: aiosqlite.Connection, session_id: str, now: str) -> None:
    await db.execute("UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (now, session_id))


async def revoke_all_for_user(db: aiosqlite.Connection, user_id: int, now: str, except_id: str | None = None) -> int:
    if except_id:
        cur = await db.execute(
            "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL AND id != ?",
            (now, user_id, except_id),
        )
    else:
        cur = await db.execute(
            "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id)
        )
    return cur.rowcount or 0


async def list_active_for_user(db: aiosqlite.Connection, user_id: int, now: str) -> list[dict[str, Any]]:
    return await fetch_all(
        db,
        """SELECT * FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
           ORDER BY last_used_at DESC""",
        (user_id, now),
    )


async def delete_expired(db: aiosqlite.Connection, before: str) -> int:
    cur = await db.execute("DELETE FROM sessions WHERE expires_at < ? OR revoked_at < ?", (before, before))
    return cur.rowcount or 0
