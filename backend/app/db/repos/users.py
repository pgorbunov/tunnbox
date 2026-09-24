"""Users and recovery codes."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one, fetch_value

USER_COLUMNS = (
    "id, username, password_hash, role, is_active, totp_secret_enc, totp_enabled, failed_logins, "
    "locked_until, last_login_at, password_changed_at, created_at, updated_at"
)


async def count(db: aiosqlite.Connection) -> int:
    return int(await fetch_value(db, "SELECT COUNT(*) FROM users") or 0)


async def get(db: aiosqlite.Connection, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(db, f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,))


async def get_by_username(db: aiosqlite.Connection, username: str) -> dict[str, Any] | None:
    return await fetch_one(db, f"SELECT {USER_COLUMNS} FROM users WHERE username = ? COLLATE NOCASE", (username,))


async def list_all(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    return await fetch_all(db, f"SELECT {USER_COLUMNS} FROM users ORDER BY id")


async def create(db: aiosqlite.Connection, username: str, password_hash: str, role: str, now: str) -> dict[str, Any]:
    cur = await db.execute(
        """INSERT INTO users (username, password_hash, role, is_active, password_changed_at, created_at, updated_at)
           VALUES (?, ?, ?, 1, ?, ?, ?)""",
        (username, password_hash, role, now, now, now),
    )
    user = await get(db, int(cur.lastrowid or 0))
    assert user is not None
    return user


async def update_fields(db: aiosqlite.Connection, user_id: int, now: str, **fields: Any) -> None:
    """Update whitelisted columns; ignores unknown keys."""
    allowed = {
        "password_hash", "role", "is_active", "totp_secret_enc", "totp_enabled", "failed_logins",
        "locked_until", "last_login_at", "password_changed_at",
    }
    items = [(k, v) for k, v in fields.items() if k in allowed]
    if not items:
        return
    assignments = ", ".join(f"{k} = ?" for k, _ in items)
    params = [v for _, v in items] + [now, user_id]
    await db.execute(f"UPDATE users SET {assignments}, updated_at = ? WHERE id = ?", params)  # noqa: S608


async def delete(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))


async def count_active_admins(db: aiosqlite.Connection, exclude_id: int | None = None) -> int:
    if exclude_id is None:
        return int(await fetch_value(db, "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1") or 0)
    return int(
        await fetch_value(
            db, "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1 AND id != ?", (exclude_id,)
        )
        or 0
    )


# --- recovery codes ---------------------------------------------------------


async def replace_recovery_codes(db: aiosqlite.Connection, user_id: int, code_hashes: list[str]) -> None:
    await db.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    await db.executemany(
        "INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, ?)",
        [(user_id, h) for h in code_hashes],
    )


async def unused_recovery_codes(db: aiosqlite.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        db, "SELECT id, code_hash FROM recovery_codes WHERE user_id = ? AND used_at IS NULL", (user_id,)
    )


async def mark_recovery_code_used(db: aiosqlite.Connection, code_id: int, now: str) -> None:
    await db.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?", (now, code_id))


async def clear_recovery_codes(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
