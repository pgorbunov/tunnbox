"""Versioned schema migrations, applied at startup."""

from __future__ import annotations

import json
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
    totp_last_step INTEGER,
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

CREATE TABLE refresh_token_history (
    refresh_hash TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rotated_at TEXT NOT NULL
);

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
CREATE UNIQUE INDEX idx_peers_interface_allowed_ips ON peers(interface_id, allowed_ips);

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

CREATE TABLE mfa_tokens_used (
    jti TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL
);
"""

LEGACY_ACTION_MAP = {
    "login": "auth.login",
    "login_failed": "auth.login_failed",
    "logout": "auth.logout",
    "setup": "auth.setup",
    "password_change": "auth.password_changed",
    "change_password": "auth.password_changed",
    "create_interface": "interface.created",
    "delete_interface": "interface.deleted",
    "toggle_interface": "interface.updated",
    "interface_up": "interface.up",
    "interface_down": "interface.down",
    "add_peer": "peer.created",
    "create_peer": "peer.created",
    "delete_peer": "peer.deleted",
    "remove_peer": "peer.deleted",
    "update_settings": "settings.updated",
    "export_data": "system.export",
}


async def _table_exists(db: aiosqlite.Connection, name: str) -> bool:
    return await fetch_value(db, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)) is not None


async def _columns(db: aiosqlite.Connection, table: str) -> set[str]:
    rows = await fetch_all(db, f"PRAGMA table_info({table})")  # noqa: S608 - table name is a constant
    return {r["name"] for r in rows}


def _statements(script: str) -> list[str]:
    return [stmt.strip() for stmt in script.split(";") if stmt.strip()]


def _dedupe_username(name: str, seen: set[str]) -> str:
    candidate, suffix = name, 2
    while candidate.lower() in seen:
        candidate = f"{name}_{suffix}"
        suffix += 1
    seen.add(candidate.lower())
    if candidate != name:
        logger.warning("Legacy username %r collides case-insensitively; migrated as %r", name, candidate)
    return candidate


def _legacy_details(raw: object) -> str | None:
    if raw in (None, ""):
        return None
    try:
        parsed = json.loads(str(raw))
    except ValueError:
        parsed = None
    return json.dumps(parsed if isinstance(parsed, dict) else {"legacy": str(raw)})


async def migration_1(db: aiosqlite.Connection, now: str) -> None:
    """Create the v2 schema; migrate a legacy v1 database in place when detected.

    Runs inside the caller's transaction (statements are executed one by one,
    never via `executescript`, which would commit implicitly).
    """
    legacy = await _table_exists(db, "peer_metadata") or await _table_exists(db, "refresh_tokens")
    legacy_users: list[dict] = []
    legacy_audit: list[dict] = []
    legacy_settings: list[dict] = []
    if legacy:
        if await _table_exists(db, "users") and "hashed_password" in await _columns(db, "users"):
            legacy_users = await fetch_all(db, "SELECT * FROM users ORDER BY id")
            await db.execute("DROP TABLE users")
        if await _table_exists(db, "audit_logs"):
            legacy_audit = await fetch_all(db, "SELECT * FROM audit_logs ORDER BY id")
            await db.execute("DROP TABLE audit_logs")
        if await _table_exists(db, "settings"):
            legacy_settings = await fetch_all(db, "SELECT key, value FROM settings")
            await db.execute("DROP TABLE settings")
        await db.execute("DROP TABLE IF EXISTS refresh_tokens")

    for statement in _statements(SCHEMA_V1):
        await db.execute(statement)

    id_map: dict[int, tuple[int, str]] = {}
    seen: set[str] = set()
    for user in legacy_users:
        username = _dedupe_username(str(user["username"]), seen)
        role = "admin" if user.get("is_admin") else "viewer"
        cur = await db.execute(
            """INSERT INTO users (username, password_hash, role, is_active, password_changed_at, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?, ?)""",
            (username, user["hashed_password"], role, now, str(user.get("created_at") or now), now),
        )
        id_map[int(user["id"])] = (int(cur.lastrowid or 0), username)
    for entry in legacy_audit:
        mapped = id_map.get(int(entry["user_id"])) if entry.get("user_id") is not None else None
        action = str(entry.get("action") or "unknown")
        await db.execute(
            "INSERT INTO audit_logs (user_id, username, action, target, details, ip, created_at) VALUES (?, ?, ?, NULL, ?, ?, ?)",
            (
                mapped[0] if mapped else None,
                mapped[1] if mapped else None,
                LEGACY_ACTION_MAP.get(action, f"legacy.{action}"),
                _legacy_details(entry.get("details")),
                entry.get("ip_address"),
                str(entry.get("created_at") or now),
            ),
        )
    for row in legacy_settings:
        key = {"wg_default_dns": "default_dns"}.get(row["key"], row["key"])
        await db.execute("INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (key, row["value"], now))
    if legacy:
        logger.info("Migrated legacy v1 database (%d users, %d audit rows)", len(legacy_users), len(legacy_audit))


MIGRATIONS: list[tuple[int, Callable[[aiosqlite.Connection, str], Awaitable[None]]]] = [
    (1, migration_1),
]


async def run_migrations(db: aiosqlite.Connection, now: str) -> int:
    """Apply pending migrations, each in its own explicit write transaction."""
    current = 0
    if await _table_exists(db, "schema_version"):
        current = int(await fetch_value(db, "SELECT COALESCE(MAX(version), 0) FROM schema_version") or 0)
    for version, fn in MIGRATIONS:
        if version <= current:
            continue
        if not db.in_transaction:
            await db.execute("BEGIN IMMEDIATE")
        try:
            await fn(db, now)
            await db.execute("DELETE FROM schema_version")
            await db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        current = version
        logger.info("Applied database migration %d", version)
    return current
