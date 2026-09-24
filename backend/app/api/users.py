"""/api/users — admin user management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import Ctx, require
from app.schemas.users import User, UserCreate, UserUpdate
from app.services import mfa as mfa_service
from app.services import users as service
from app.services.auth import Principal

router = APIRouter(prefix="/users", tags=["users"])
Admin = Annotated[Principal, Depends(require("admin", "admin"))]


@router.get("", response_model=list[User])
async def list_users(_: Admin, ctx: Ctx) -> list[User]:
    return [User(**u) for u in await service.list_users(ctx)]


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, principal: Admin, ctx: Ctx) -> User:
    return User(**await service.create_user(ctx, principal, body))


@router.patch("/{user_id}", response_model=User)
async def update_user(user_id: int, body: UserUpdate, principal: Admin, ctx: Ctx) -> User:
    return User(**await service.update_user(ctx, principal, user_id, body))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, principal: Admin, ctx: Ctx) -> Response:
    await service.delete_user(ctx, principal, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/mfa/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_mfa(user_id: int, principal: Admin, ctx: Ctx) -> Response:
    await mfa_service.admin_reset(ctx, principal.actor, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
