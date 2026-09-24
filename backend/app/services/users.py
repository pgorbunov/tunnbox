"""Admin user management with self-protection guards."""

from __future__ import annotations

from typing import Any

from app.context import AppContext
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.security import hash_password, now_iso, validate_password_policy
from app.db.connection import connect
from app.db.repos import users as repo
from app.schemas.users import UserCreate, UserUpdate
from app.services import audit
from app.services.auth import Principal, revoke_everything_for_user, user_response


async def list_users(ctx: AppContext) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        return [user_response(u) for u in await repo.list_all(db)]


async def create_user(ctx: AppContext, principal: Principal, data: UserCreate) -> dict[str, Any]:
    error = validate_password_policy(data.password, data.username)
    if error:
        raise BadRequest(error, code="weak_password")
    async with connect(ctx.db_path) as db:
        if await repo.get_by_username(db, data.username):
            raise Conflict("Username already exists")
        user = await repo.create(db, data.username, hash_password(data.password, ctx.settings.bcrypt_rounds), data.role, now_iso())
        await audit.add(db, principal.actor, "user.created", target=user["username"], details={"role": data.role})
        return user_response(user)


async def update_user(ctx: AppContext, principal: Principal, user_id: int, data: UserUpdate) -> dict[str, Any]:
    changes = data.model_dump(exclude_unset=True)
    async with connect(ctx.db_path) as db:
        user = await repo.get(db, user_id)
        if user is None:
            raise NotFound("User not found")
        is_self = user_id == principal.user_id
        demoting = changes.get("role") not in (None, "admin") and user["role"] == "admin"
        disabling = changes.get("is_active") is False and user["is_active"]
        if is_self and (demoting or disabling):
            raise BadRequest("You cannot demote or disable your own account", code="self_guard")
        if (demoting or disabling) and user["role"] == "admin" and user["is_active"]:
            if await repo.count_active_admins(db, exclude_id=user_id) == 0:
                raise BadRequest("Cannot remove the last active admin", code="last_admin")
        fields: dict[str, Any] = {}
        if "role" in changes and changes["role"] is not None:
            fields["role"] = changes["role"]
        if "is_active" in changes and changes["is_active"] is not None:
            fields["is_active"] = 1 if changes["is_active"] else 0
        if changes.get("password"):
            error = validate_password_policy(changes["password"], user["username"])
            if error:
                raise BadRequest(error, code="weak_password")
            fields["password_hash"] = hash_password(changes["password"], ctx.settings.bcrypt_rounds)
            fields["password_changed_at"] = now_iso()
        if fields:
            await repo.update_fields(db, user_id, now_iso(), **fields)
        if disabling or "password_hash" in fields or "role" in fields:
            await revoke_everything_for_user(db, user_id)
        updated = await repo.get(db, user_id)
        assert updated is not None
        await audit.add(db, principal.actor, "user.updated", target=user["username"], details={"fields": sorted(k for k in fields if k != "password_hash") + (["password"] if "password_hash" in fields else [])})
        return user_response(updated)


async def delete_user(ctx: AppContext, principal: Principal, user_id: int) -> None:
    async with connect(ctx.db_path) as db:
        user = await repo.get(db, user_id)
        if user is None:
            raise NotFound("User not found")
        if user_id == principal.user_id:
            raise BadRequest("You cannot delete your own account", code="self_guard")
        if user["role"] == "admin" and user["is_active"] and await repo.count_active_admins(db, exclude_id=user_id) == 0:
            raise BadRequest("Cannot remove the last active admin", code="last_admin")
        await repo.delete(db, user_id)
        await audit.add(db, principal.actor, "user.deleted", target=user["username"])
