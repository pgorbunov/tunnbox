"""WireGuard interfaces (desired state)."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_one, fetch_value

UPDATABLE = {"address", "listen_port", "dns", "mtu", "post_up", "post_down", "public_endpoint", "enabled"}


async def list_all(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    return await fetch_all(db, "SELECT * FROM interfaces ORDER BY name")


async def get(db: aiosqlite.Connection, interface_id: int) -> dict[str, Any] | None:
    return await fetch_one(db, "SELECT * FROM interfaces WHERE id = ?", (interface_id,))


async def get_by_name(db: aiosqlite.Connection, name: str) -> dict[str, Any] | None:
    return await fetch_one(db, "SELECT * FROM interfaces WHERE name = ?", (name,))


async def port_in_use(db: aiosqlite.Connection, port: int, exclude_id: int | None = None) -> bool:
    if exclude_id is None:
        return await fetch_value(db, "SELECT 1 FROM interfaces WHERE listen_port = ?", (port,)) is not None
    return (
        await fetch_value(db, "SELECT 1 FROM interfaces WHERE listen_port = ? AND id != ?", (port, exclude_id))
        is not None
    )


async def create(db: aiosqlite.Connection, now: str, **fields: Any) -> dict[str, Any]:
    cur = await db.execute(
        """INSERT INTO interfaces (name, private_key_enc, public_key, address, listen_port, dns, mtu,
                                   post_up, post_down, public_endpoint, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            fields["name"], fields["private_key_enc"], fields["public_key"], fields["address"],
            fields["listen_port"], fields.get("dns"), fields.get("mtu"), fields.get("post_up"),
            fields.get("post_down"), fields.get("public_endpoint"), 1 if fields.get("enabled", True) else 0,
            now, now,
        ),
    )
    row = await get(db, int(cur.lastrowid or 0))
    assert row is not None
    return row


async def update(db: aiosqlite.Connection, interface_id: int, now: str, **fields: Any) -> None:
    items = [(k, v) for k, v in fields.items() if k in UPDATABLE]
    if not items:
        return
    assignments = ", ".join(f"{k} = ?" for k, _ in items)
    params = [int(v) if k == "enabled" else v for k, v in items] + [now, interface_id]
    await db.execute(f"UPDATE interfaces SET {assignments}, updated_at = ? WHERE id = ?", params)  # noqa: S608


async def delete(db: aiosqlite.Connection, interface_id: int) -> None:
    await db.execute("DELETE FROM interfaces WHERE id = ?", (interface_id,))


async def peer_summary(db: aiosqlite.Connection, interface_id: int, online_since: str) -> dict[str, int]:
    """Peer counts and traffic totals for one interface."""
    row = await fetch_one(
        db,
        """SELECT COUNT(*) AS peer_count,
                  COALESCE(SUM(CASE WHEN enabled = 1 AND last_handshake_at >= ? THEN 1 ELSE 0 END), 0) AS online,
                  COALESCE(SUM(rx_total), 0) AS rx_total, COALESCE(SUM(tx_total), 0) AS tx_total
           FROM peers WHERE interface_id = ?""",
        (online_since, interface_id),
    )
    assert row is not None
    return {
        "peer_count": int(row["peer_count"]),
        "online_peer_count": int(row["online"]),
        "rx_total": int(row["rx_total"]),
        "tx_total": int(row["tx_total"]),
    }
