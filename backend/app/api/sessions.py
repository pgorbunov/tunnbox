"""/api/auth/sessions — list and revoke login sessions."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import Ctx, SessionPrincipal
from app.schemas.auth import Session
from app.services import auth as auth_service

router = APIRouter(prefix="/auth/sessions", tags=["auth"])


@router.get("", response_model=list[Session])
async def list_sessions(principal: SessionPrincipal, ctx: Ctx) -> list[Session]:
    return [Session(**s) for s in await auth_service.list_sessions(ctx, principal)]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_others(principal: SessionPrincipal, ctx: Ctx) -> Response:
    await auth_service.revoke_other_sessions(ctx, principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: str, principal: SessionPrincipal, ctx: Ctx) -> Response:
    await auth_service.revoke_session(ctx, principal, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
