"""Versioned schema migrations, applied at startup."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import aiosqlite

from app.db.connection import fetch_all, fetch_value

logger = logging.getLogger(__name__)

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'operator', 'viewer')),
    is_active INTEGER NOT NULL DEFAULT 1,
    totp_secret_enc TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    last_login_at TEXT,
    password_changed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    used_at TEXT
);
CREATE INDEX idx_recovery_codes_user ON recovery_codes(user_id);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_hash TEXT NOT NULL UNIQUE,
    ip TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at TEXT,
    last_used_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    private_key_enc TEXT NOT NULL,
    public_key TEXT NOT NULL,
    address TEXT NOT NULL,
    listen_port INTEGER NOT NULL UNIQUE,
    dns TEXT,
    mtu INTEGER,
    post_up TEXT,
    post_down TEXT,
    public_endpoint TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER NOT NULL REFERENCES interfaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    private_key_enc TEXT,
    preshared_key_enc TEXT,
    allowed_ips TEXT NOT NULL,
    client_allowed_ips TEXT NOT NULL,
    client_dns TEXT,
    persistent_keepalive INTEGER NOT NULL DEFAULT 25,
    enabled INTEGER NOT NULL DEFAULT 1,
    expires_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_handshake_at TEXT,
    rx_total INTEGER NOT NULL DEFAULT 0,
    tx_total INTEGER NOT NULL DEFAULT 0,
    UNIQUE (interface_id, public_key)
);
CREATE INDEX idx_peers_interface ON peers(interface_id);

CREATE TABLE peer_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL REFERENCES peers(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    rx_delta INTEGER NOT NULL DEFAULT 0,
    tx_delta INTEGER NOT NULL DEFAULT 0,
    online INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_peer_stats_peer_ts ON peer_stats(peer_id, ts);
CREATE INDEX idx_peer_stats_ts ON peer_stats(ts);

CREATE TABLE share_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER NOT NULL REFERENCES peers(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_by INTEGER,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    max_uses INTEGER NOT NULL DEFAULT 1,
    uses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    target TEXT,
    details TEXT,
    ip TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def _table_exists(db: aiosqlite.Connection, name: str) -> bool:
    return await fetch_value(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)) is not None


async def _columns(db: aiosqlite.Connection, table: str) -> set[str]:
    rows = await fetch_all(db, f"PRAGMA table_info({table})")  # noqa: S608 - table name is a constant
    return {r["name"] for r in rows}


async def migration_1(db: aiosqlite.Connection, now: str) -> None:
    """Create the v2 schema; migrate a legacy v1 database in place when detected."""
    legacy = await _table_exists(db, "peer_metadata") or await _table_exists(db, "refresh_tokens")
    legacy_users: list[dict] = []
    if legacy and await _table_exists(db, "users"):
        cols = await _columns(db, "users")
        if "hashed_password" in cols:
            legacy_users = await fetch_all(db, "SELECT * FROM users")
            await db.execute("ALTER TABLE users RENAME TO users_v1")
        if await _table_exists(db, "audit_logs"):
            await db.execute("ALTER TABLE audit_logs RENAME TO audit_logs_v1")
        if await _table_exists(db, "settings"):
            await db.execute("ALTER TABLE settings RENAME TO settings_v1")
        await db.execute("DROP TABLE IF EXISTS refresh_tokens")

    await db.executescript(SCHEMA_V1)

    for user in legacy_users:
        await db.execute(
            """INSERT INTO users (username, password_hash, role, is_active, password_changed_at, created_at, updated_at)
               VALUES (?, ?, 'admin', 1, ?, ?, ?)""",
            (user["username"], user["hashed_password"], now, str(user.get("created_at") or now), now),
        )
    if legacy:
        if await _table_exists(db, "settings_v1"):
            rows = await fetch_all(db, "SELECT key, value FROM settings_v1")
            for row in rows:
                key = {"wg_default_dns": "default_dns"}.get(row["key"], row["key"])
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, row["value"], now),
                )
            await db.execute("DROP TABLE settings_v1")
        await db.execute("DROP TABLE IF EXISTS users_v1")
        await db.execute("DROP TABLE IF EXISTS audit_logs_v1")
        logger.info("Migrated legacy v1 database (%d users)", len(legacy_users))


MIGRATIONS: list[tuple[int, Callable[[aiosqlite.Connection, str], Awaitable[None]]]] = [
    (1, migration_1),
]


async def run_migrations(db: aiosqlite.Connection, now: str) -> int:
    """Apply pending migrations and return the resulting schema version."""
    current = 0
    if await _table_exists(db, "schema_version"):
        current = int(await fetch_value(db, "SELECT COALESCE(MAX(version), 0) FROM schema_version") or 0)
    for version, fn in MIGRATIONS:
        if version <= current:
            continue
        await fn(db, now)
        await db.execute("DELETE FROM schema_version")
        await db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        await db.commit()
        current = version
        logger.info("Applied database migration %d", version)
    return current
