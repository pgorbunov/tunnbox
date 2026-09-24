"""SQLite connection helper (WAL, foreign keys, Row factory, auto commit)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

Row = aiosqlite.Row


@asynccontextmanager
async def connect(path: Path | str) -> AsyncIterator[aiosqlite.Connection]:
    """Open a connection; commit on clean exit, roll back on error."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(path), timeout=30)
    try:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
    finally:
        await db.close()


async def fetch_one(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    async with db.execute(sql, params) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def fetch_all(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def fetch_value(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    async with db.execute(sql, params) as cur:
        row = await cur.fetchone()
    return row[0] if row else None
