"""Peers."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one, fetch_value

UPDATABLE = {
    "name", "public_key", "private_key_enc", "preshared_key_enc", "allowed_ips", "client_allowed_ips",
    "client_dns", "persistent_keepalive", "enabled", "expires_at", "notes", "last_handshake_at",
    "rx_total", "tx_total",
}
SORT_COLUMNS = {
    "name": "p.name COLLATE NOCASE",
    "handshake": "p.last_handshake_at",
    "rx": "p.rx_total",
    "tx": "p.tx_total",
    "created": "p.created_at",
}

_SELECT = "SELECT p.*, i.name AS interface_name FROM peers p JOIN interfaces i ON i.id = p.interface_id"


async def get(db: aiosqlite.Connection, peer_id: int) -> dict[str, Any] | None:
    return await fetch_one(db, f"{_SELECT} WHERE p.id = ?", (peer_id,))


async def get_by_public_key(db: aiosqlite.Connection, interface_id: int, public_key: str) -> dict[str, Any] | None:
    return await fetch_one(db, f"{_SELECT} WHERE p.interface_id = ? AND p.public_key = ?", (interface_id, public_key))


async def list_for_interface(
    db: aiosqlite.Connection,
    interface_id: int,
    *,
    q: str | None = None,
    sort: str = "name",
    order: str = "asc",
) -> list[dict[str, Any]]:
    where = ["p.interface_id = ?"]
    params: list[Any] = [interface_id]
    if q:
        where.append("(p.name LIKE ? OR p.allowed_ips LIKE ? OR p.public_key LIKE ? OR p.notes LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like, like]
    column = SORT_COLUMNS.get(sort, SORT_COLUMNS["name"])
    direction = "DESC" if order.lower() == "desc" else "ASC"
    sql = f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY {column} {direction}, p.id ASC"  # noqa: S608
    return await fetch_all(db, sql, tuple(params))


async def list_all(db: aiosqlite.Connection, *, q: str | None = None, interface: str | None = None) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if interface:
        where.append("i.name = ?")
        params.append(interface)
    if q:
        where.append("(p.name LIKE ? OR p.allowed_ips LIKE ? OR p.public_key LIKE ? OR p.notes LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like, like]
    sql = f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY i.name, p.name COLLATE NOCASE, p.id"  # noqa: S608
    return await fetch_all(db, sql, tuple(params))


async def list_by_ids(db: aiosqlite.Connection, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    return await fetch_all(db, f"{_SELECT} WHERE p.id IN ({placeholders})", tuple(ids))  # noqa: S608


async def create(db: aiosqlite.Connection, now: str, **f: Any) -> dict[str, Any]:
    cur = await db.execute(
        """INSERT INTO peers (interface_id, name, public_key, private_key_enc, preshared_key_enc, allowed_ips,
                              client_allowed_ips, client_dns, persistent_keepalive, enabled, expires_at, notes,
                              created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f["interface_id"], f["name"], f["public_key"], f.get("private_key_enc"), f.get("preshared_key_enc"),
            f["allowed_ips"], f["client_allowed_ips"], f.get("client_dns"), int(f.get("persistent_keepalive", 25)),
            1 if f.get("enabled", True) else 0, f.get("expires_at"), f.get("notes"), now, now,
        ),
    )
    row = await get(db, int(cur.lastrowid or 0))
    assert row is not None
    return row


async def update(db: aiosqlite.Connection, peer_id: int, now: str | None, **fields: Any) -> None:
    items = [(k, v) for k, v in fields.items() if k in UPDATABLE]
    if not items:
        return
    assignments = ", ".join(f"{k} = ?" for k, _ in items)
    params: list[Any] = [int(v) if k == "enabled" else v for k, v in items]
    if now is not None:
        assignments += ", updated_at = ?"
        params.append(now)
    params.append(peer_id)
    await db.execute(f"UPDATE peers SET {assignments} WHERE id = ?", params)  # noqa: S608


async def delete(db: aiosqlite.Connection, peer_id: int) -> None:
    await db.execute("DELETE FROM peers WHERE id = ?", (peer_id,))


async def expired_enabled(db: aiosqlite.Connection, now: str) -> list[dict[str, Any]]:
    return await fetch_all(db, f"{_SELECT} WHERE p.enabled = 1 AND p.expires_at IS NOT NULL AND p.expires_at <= ?", (now,))


async def overview_counts(db: aiosqlite.Connection, now: str, online_since: str, expiring_before: str) -> dict[str, int]:
    row = await fetch_one(
        db,
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN enabled = 1 AND last_handshake_at >= ? THEN 1 ELSE 0 END), 0) AS online,
                  COALESCE(SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END), 0) AS disabled,
                  COALESCE(SUM(CASE WHEN enabled = 1 AND expires_at IS NOT NULL AND expires_at > ? AND expires_at <= ?
                                    THEN 1 ELSE 0 END), 0) AS expiring,
                  COALESCE(SUM(rx_total), 0) AS rx_total, COALESCE(SUM(tx_total), 0) AS tx_total
           FROM peers""",
        (online_since, now, expiring_before),
    )
    assert row is not None
    return {k: int(row[k]) for k in ("total", "online", "disabled", "expiring", "rx_total", "tx_total")}


async def count_for_interface(db: aiosqlite.Connection, interface_id: int) -> int:
    return int(await fetch_value(db, "SELECT COUNT(*) FROM peers WHERE interface_id = ?", (interface_id,)) or 0)
