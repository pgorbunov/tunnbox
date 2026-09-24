"""/api/share/{token} — public, rate-limited retrieval of a shared peer config."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import Ctx, client_ip, rate_limit
from app.schemas.share import SharePayload
from app.services import share as service

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}", response_model=SharePayload, dependencies=[Depends(rate_limit("share", 20, 60))])
async def redeem(token: str, request: Request, ctx: Ctx) -> SharePayload:
    return SharePayload(**await service.redeem(ctx, token, client_ip(request)))
