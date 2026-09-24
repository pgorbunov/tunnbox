"""Peer traffic samples and bucketed queries."""

from __future__ import annotations

from typing import Any

import aiosqlite

from app.db.connection import fetch_all


async def insert_sample(db: aiosqlite.Connection, peer_id: int, ts: str, rx_delta: int, tx_delta: int, online: bool) -> None:
    await db.execute(
        "INSERT INTO peer_stats (peer_id, ts, rx_delta, tx_delta, online) VALUES (?, ?, ?, ?, ?)",
        (peer_id, ts, rx_delta, tx_delta, 1 if online else 0),
    )


def _peer_filter(interface_id: int | None, peer_id: int | None) -> tuple[str, list[Any]]:
    if peer_id is not None:
        return "s.peer_id = ?", [peer_id]
    if interface_id is not None:
        return "s.peer_id IN (SELECT id FROM peers WHERE interface_id = ?)", [interface_id]
    return "1=1", []


async def bucketed(
    db: aiosqlite.Connection,
    *,
    since: str,
    bucket_seconds: int,
    interface_id: int | None = None,
    peer_id: int | None = None,
) -> list[dict[str, Any]]:
    """Sum deltas per time bucket; `online` is the number of distinct peers seen online."""
    where, params = _peer_filter(interface_id, peer_id)
    sql = f"""
        SELECT (CAST(strftime('%s', s.ts) AS INTEGER) / ?) * ? AS bucket,
               COALESCE(SUM(s.rx_delta), 0) AS rx, COALESCE(SUM(s.tx_delta), 0) AS tx,
               COUNT(DISTINCT CASE WHEN s.online = 1 THEN s.peer_id END) AS online
        FROM peer_stats s WHERE s.ts >= ? AND {where}
        GROUP BY bucket ORDER BY bucket
    """  # noqa: S608
    return await fetch_all(db, sql, (bucket_seconds, bucket_seconds, since, *params))


async def top_peers(db: aiosqlite.Connection, since: str, limit: int = 5) -> list[dict[str, Any]]:
    return await fetch_all(
        db,
        """SELECT p.id AS peer_id, p.name, i.name AS interface_name,
                  COALESCE(SUM(s.rx_delta), 0) AS rx, COALESCE(SUM(s.tx_delta), 0) AS tx
           FROM peer_stats s JOIN peers p ON p.id = s.peer_id JOIN interfaces i ON i.id = p.interface_id
           WHERE s.ts >= ? GROUP BY p.id ORDER BY (rx + tx) DESC, p.id LIMIT ?""",
        (since, limit),
    )


async def delete_before(db: aiosqlite.Connection, before: str) -> int:
    cur = await db.execute("DELETE FROM peer_stats WHERE ts < ?", (before,))
    return cur.rowcount or 0
