"""/api/mfa — TOTP setup, enable, disable, recovery codes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import Ctx, SessionPrincipal
from app.schemas.mfa import (
    MfaDisableRequest,
    MfaEnableRequest,
    MfaPasswordRequest,
    MfaSetupRequest,
    MfaSetupResponse,
    RecoveryCodes,
)
from app.services import mfa as mfa_service

router = APIRouter(prefix="/mfa", tags=["mfa"])


@router.post("/setup", response_model=MfaSetupResponse)
async def setup(body: MfaSetupRequest, principal: SessionPrincipal, ctx: Ctx) -> MfaSetupResponse:
    return MfaSetupResponse(**await mfa_service.setup(ctx, principal, body.password))


@router.post("/enable", response_model=RecoveryCodes)
async def enable(body: MfaEnableRequest, principal: SessionPrincipal, ctx: Ctx) -> RecoveryCodes:
    return RecoveryCodes(recovery_codes=await mfa_service.enable(ctx, principal, body.password, body.code))


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable(body: MfaDisableRequest, principal: SessionPrincipal, ctx: Ctx) -> Response:
    await mfa_service.disable(ctx, principal, body.password, body.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/recovery-codes", response_model=RecoveryCodes)
async def regenerate(body: MfaPasswordRequest, principal: SessionPrincipal, ctx: Ctx) -> RecoveryCodes:
    return RecoveryCodes(recovery_codes=await mfa_service.regenerate_recovery_codes(ctx, principal, body.password))
