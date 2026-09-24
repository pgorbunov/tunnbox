"""/api/audit — query, distinct actions and CSV export (operator+)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import Ctx, require
from app.schemas.audit import AuditEntry
from app.schemas.common import Page
from app.services import audit as service
from app.services.auth import Principal

router = APIRouter(prefix="/audit", tags=["audit"])
Operator = Annotated[Principal, Depends(require("operator", "read"))]


def _filters(
    action: str | None = Query(default=None, max_length=64),
    username: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=200),
    target: str | None = Query(default=None, max_length=200),
    from_: str | None = Query(default=None, alias="from", max_length=40),
    to: str | None = Query(default=None, max_length=40),
) -> dict[str, Any]:
    return {"action": action, "username": username, "q": q, "target": target, "from_ts": from_, "to_ts": to}


Filters = Annotated[dict[str, Any], Depends(_filters)]


@router.get("", response_model=Page[AuditEntry])
async def query(_: Operator, ctx: Ctx, filters: Filters, page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500)) -> Page[AuditEntry]:
    items, total = await service.query(ctx, filters, page, page_size)
    return Page[AuditEntry](items=[AuditEntry(**i) for i in items], total=total, page=page, page_size=page_size)


@router.get("/actions", response_model=list[str])
async def actions(_: Operator, ctx: Ctx) -> list[str]:
    return await service.actions(ctx)


@router.get("/export.csv")
async def export_csv(_: Operator, ctx: Ctx, filters: Filters) -> Response:
    csv_text = await service.export_csv(ctx, filters)
    return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit.csv"'})
