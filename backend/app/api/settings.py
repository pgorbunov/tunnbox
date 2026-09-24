"""/api/settings — runtime settings (GET any role, PATCH admin)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Ctx, require
from app.core.security import now_iso
from app.db.connection import connect
from app.db.repos import settings as repo
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services import audit
from app.services.auth import Principal

router = APIRouter(prefix="/settings", tags=["settings"])
Reader = Annotated[Principal, Depends(require("viewer", "read"))]
Admin = Annotated[Principal, Depends(require("admin", "admin"))]


@router.get("", response_model=SettingsResponse)
async def get_settings(_: Reader, ctx: Ctx) -> SettingsResponse:
    async with connect(ctx.db_path) as db:
        values = await repo.get_all(db)
    return SettingsResponse(**values, custom_scripts_allowed=ctx.settings.wg_allow_custom_scripts)


@router.patch("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, principal: Admin, ctx: Ctx) -> SettingsResponse:
    changes = body.model_dump(exclude_unset=True)
    async with connect(ctx.db_path) as db:
        if changes:
            await repo.set_many(db, changes, now_iso())
            await audit.add(db, principal.actor, "settings.updated", target="settings", details={"fields": sorted(changes)})
        values = await repo.get_all(db)
    return SettingsResponse(**values, custom_scripts_allowed=ctx.settings.wg_allow_custom_scripts)
