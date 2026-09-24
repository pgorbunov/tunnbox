"""/api/api-keys — session principals manage their scoped keys."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from app.api.deps import Ctx, SessionPrincipal
from app.schemas.api_keys import ApiKey, ApiKeyCreate, ApiKeyCreated
from app.services import api_keys as service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKey])
async def list_keys(principal: SessionPrincipal, ctx: Ctx, all: bool = Query(default=False)) -> list[ApiKey]:  # noqa: A002
    return [ApiKey(**k) for k in await service.list_keys(ctx, principal, include_all=all)]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(body: ApiKeyCreate, principal: SessionPrincipal, ctx: Ctx) -> ApiKeyCreated:
    return ApiKeyCreated(**await service.create_key(ctx, principal, body))


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(key_id: int, principal: SessionPrincipal, ctx: Ctx) -> Response:
    await service.revoke_key(ctx, principal, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
