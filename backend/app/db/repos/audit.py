"""Audit log."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.db.connection import fetch_all, fetch_value


async def add(
    db: aiosqlite.Connection,
    *,
    action: str,
    now: str,
    user_id: int | None = None,
    username: str | None = None,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO audit_logs (user_id, username, action, target, details, ip, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, action, target, json.dumps(details) if details is not None else None, ip, now),
    )


def _build_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if filters.get("action"):
        where.append("action = ?")
        params.append(filters["action"])
    if filters.get("username"):
        where.append("username = ? COLLATE NOCASE")
        params.append(filters["username"])
    if filters.get("target"):
        where.append("target = ?")
        params.append(filters["target"])
    if filters.get("q"):
        like = f"%{filters['q']}%"
        where.append("(target LIKE ? OR details LIKE ? OR username LIKE ? OR action LIKE ?)")
        params += [like, like, like, like]
    if filters.get("from_ts"):
        where.append("created_at >= ?")
        params.append(filters["from_ts"])
    if filters.get("to_ts"):
        where.append("created_at <= ?")
        params.append(filters["to_ts"])
    return " AND ".join(where), params


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("details"):
        try:
            row["details"] = json.loads(row["details"])
        except ValueError:
            row["details"] = {"raw": row["details"]}
    else:
        row["details"] = None
    return row


async def query(db: aiosqlite.Connection, filters: dict[str, Any], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    where, params = _build_where(filters)
    total = int(await fetch_value(db, f"SELECT COUNT(*) FROM audit_logs WHERE {where}", tuple(params)) or 0)  # noqa: S608
    rows = await fetch_all(
        db,
        f"SELECT * FROM audit_logs WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",  # noqa: S608
        (*params, page_size, (page - 1) * page_size),
    )
    return [_decode(r) for r in rows], total


async def iterate(db: aiosqlite.Connection, filters: dict[str, Any], limit: int = 100_000) -> list[dict[str, Any]]:
    where, params = _build_where(filters)
    rows = await fetch_all(db, f"SELECT * FROM audit_logs WHERE {where} ORDER BY id DESC LIMIT ?", (*params, limit))  # noqa: S608
    return [_decode(r) for r in rows]


async def recent(db: aiosqlite.Connection, limit: int = 10) -> list[dict[str, Any]]:
    rows = await fetch_all(db, "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    return [_decode(r) for r in rows]


async def distinct_actions(db: aiosqlite.Connection) -> list[str]:
    rows = await fetch_all(db, "SELECT DISTINCT action FROM audit_logs ORDER BY action")
    return [r["action"] for r in rows]


async def delete_before(db: aiosqlite.Connection, before: str) -> int:
    cur = await db.execute("DELETE FROM audit_logs WHERE created_at < ?", (before,))
    return cur.rowcount or 0
