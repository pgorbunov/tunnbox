"""Audit logging: add entries, query, CSV export."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

import aiosqlite

from app.context import AppContext
from app.core.security import now_iso
from app.db.connection import connect
from app.db.repos import audit as audit_repo

SYSTEM_ACTOR_NAME = "system"


@dataclass(frozen=True)
class Actor:
    """Who performed an action, as recorded in the audit log."""

    user_id: int | None
    username: str | None
    ip: str | None = None

    @classmethod
    def system(cls) -> "Actor":
        return cls(user_id=None, username=SYSTEM_ACTOR_NAME, ip=None)


async def add(
    db: aiosqlite.Connection,
    actor: Actor,
    action: str,
    target: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    await audit_repo.add(
        db,
        action=action,
        now=now_iso(),
        user_id=actor.user_id,
        username=actor.username,
        target=target,
        details=details,
        ip=actor.ip,
    )


async def query(ctx: AppContext, filters: dict[str, Any], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    async with connect(ctx.db_path) as db:
        return await audit_repo.query(db, filters, page, page_size)


async def actions(ctx: AppContext) -> list[str]:
    async with connect(ctx.db_path) as db:
        return await audit_repo.distinct_actions(db)


async def export_csv(ctx: AppContext, filters: dict[str, Any]) -> str:
    async with connect(ctx.db_path) as db:
        rows = await audit_repo.iterate(db, filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "username", "user_id", "action", "target", "ip", "details"])
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["created_at"],
                _csv_safe(row["username"]),
                row["user_id"],
                _csv_safe(row["action"]),
                _csv_safe(row["target"]),
                _csv_safe(row["ip"]),
                _csv_safe(json.dumps(row["details"]) if row["details"] is not None else ""),
            ]
        )
    return buffer.getvalue()


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value
