"""Users and recovery codes."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one, fetch_value

USER_COLUMNS = (
    "id, username, password_hash, role, is_active, totp_secret_enc, totp_enabled, failed_logins, "
    "locked_until, totp_last_step, last_login_at, password_changed_at, created_at, updated_at"
)


async def count(db: aiosqlite.Connection) -> int:
    return int(await fetch_value(db, "SELECT COUNT(*) FROM users") or 0)


async def get(db: aiosqlite.Connection, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(db, f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,))


async def get_by_username(db: aiosqlite.Connection, username: str) -> dict[str, Any] | None:
    return await fetch_one(db, f"SELECT {USER_COLUMNS} FROM users WHERE username = ? COLLATE NOCASE", (username,))


async def list_all(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    return await fetch_all(db, f"SELECT {USER_COLUMNS} FROM users ORDER BY id")


async def increment_failed_logins(db: aiosqlite.Connection, user_id: int, now: str) -> int:
    """Atomic counter bump; returns the new value (no read-modify-write race)."""
    row = await fetch_one(
        db,
        "UPDATE users SET failed_logins = failed_logins + 1, updated_at = ? WHERE id = ? RETURNING failed_logins",
        (now, user_id),
    )
    return int(row["failed_logins"]) if row else 0


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
        "locked_until", "totp_last_step", "last_login_at", "password_changed_at",
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


async def spend_recovery_code(db: aiosqlite.Connection, code_id: int, now: str) -> bool:
    """Mark a code used exactly once; False when it was already spent concurrently."""
    cur = await db.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ? AND used_at IS NULL", (now, code_id))
    return (cur.rowcount or 0) == 1


async def consume_mfa_token(db: aiosqlite.Connection, jti: str, expires_at: str) -> bool:
    """Record a single-use MFA token id; False if it was already consumed."""
    try:
        await db.execute("INSERT INTO mfa_tokens_used (jti, expires_at) VALUES (?, ?)", (jti, expires_at))
    except aiosqlite.IntegrityError:
        return False
    return True


async def prune_mfa_tokens(db: aiosqlite.Connection, now: str) -> int:
    cur = await db.execute("DELETE FROM mfa_tokens_used WHERE expires_at < ?", (now,))
    return cur.rowcount or 0


async def clear_recovery_codes(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
