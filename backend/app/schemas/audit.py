"""Audit schemas."""

from __future__ import annotations

from typing import Any

from app.schemas.common import ApiModel


class AuditEntry(ApiModel):
    id: int
    user_id: int | None
    username: str | None
    action: str
    target: str | None
    details: dict[str, Any] | None
    ip: str | None
    created_at: str
