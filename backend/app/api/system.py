"""/api/system — health, info, backup, export."""

from __future__ import annotations

import platform
import socket
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from app import __version__
from app.api.deps import Ctx, require
from app.core.security import utcnow
from app.db.connection import connect
from app.schemas.system import Health, SystemInfo
from app.services import audit, backup
from app.services.auth import Principal

router = APIRouter(prefix="/system", tags=["system"])
Reader = Annotated[Principal, Depends(require("viewer", "read"))]
Admin = Annotated[Principal, Depends(require("admin", "admin"))]


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health()


@router.get("/info", response_model=SystemInfo)
async def info(_: Reader, ctx: Ctx) -> SystemInfo:
    db_path = ctx.db_path
    size = db_path.stat().st_size if db_path.exists() else 0
    return SystemInfo(
        version=__version__,
        backend_mode=ctx.backend.mode,  # type: ignore[arg-type]
        wireguard_version=await ctx.backend.version(),
        kernel_module=await ctx.backend.kernel_module(),
        python_version=platform.python_version(),
        os=f"{platform.system()} {platform.release()}",
        uptime_seconds=int(time.monotonic() - ctx.started_at),
        database_size_bytes=size,
        config_path=str(ctx.settings.config_dir),
        hostname=socket.gethostname(),
    )


@router.get("/backup")
async def download_backup(principal: Admin, ctx: Ctx) -> Response:
    data = await backup.build_backup(ctx)
    async with connect(ctx.db_path) as db:
        await audit.add(db, principal.actor, "system.backup", target="backup", details={"bytes": len(data)})
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    return Response(content=data, media_type="application/gzip", headers={"Content-Disposition": f'attachment; filename="tunnbox-backup-{stamp}.tar.gz"'})


@router.get("/export")
async def export_json(principal: Admin, ctx: Ctx) -> JSONResponse:
    data: dict[str, Any] = await backup.build_export(ctx, principal.user["username"])
    async with connect(ctx.db_path) as db:
        await audit.add(db, principal.actor, "system.export", target="export")
    return JSONResponse(content=data, headers={"Content-Disposition": 'attachment; filename="tunnbox-export.json"'})


