"""/api/stats — dashboard overview."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Ctx, require
from app.schemas.stats import Overview, StatsRange
from app.services import stats as service
from app.services.auth import Principal

router = APIRouter(prefix="/stats", tags=["stats"])
Reader = Annotated[Principal, Depends(require("viewer", "read"))]


@router.get("/overview", response_model=Overview)
async def overview(_: Reader, ctx: Ctx, range: StatsRange = "24h") -> Overview:  # noqa: A002
    return Overview(**await service.overview(ctx, range))
