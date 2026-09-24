"""Scoped API keys: `tb_<random>` shown once, sha256 stored."""

from __future__ import annotations

from typing import Any

from app.context import AppContext
from app.core.errors import BadRequest, NotFound
from app.core.security import iso, new_opaque_token, now_iso, parse_iso, sha256_hex, utcnow
from app.db.connection import connect
from app.db.repos import api_keys as repo
from app.db.repos import users as users_repo
from app.schemas.api_keys import ApiKeyCreate
from app.schemas.common import ROLE_RANK
from app.services import audit
from app.services.auth import Principal

KEY_PREFIX = "tb_"
SCOPE_MIN_ROLE = {"read": "viewer", "peers:write": "operator", "interfaces:write": "operator", "admin": "admin"}


def _response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "prefix": row["prefix"],
        "scopes": row["scopes"],
        "expires_at": row["expires_at"],
        "last_used_at": row["last_used_at"],
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"],
    }


async def list_keys(ctx: AppContext, principal: Principal, include_all: bool) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        rows = await repo.list_all(db) if include_all and principal.role == "admin" else await repo.list_for_user(db, principal.user_id)
    return [_response(r) for r in rows]


async def create_key(ctx: AppContext, principal: Principal, data: ApiKeyCreate) -> dict[str, Any]:
    for scope in data.scopes:
        if ROLE_RANK[principal.role] < ROLE_RANK[SCOPE_MIN_ROLE[scope]]:
            raise BadRequest(f"Scope '{scope}' exceeds your role", code="scope_exceeds_role")
    expires_at = None
    if data.expires_at:
        parsed = parse_iso(data.expires_at)
        if parsed is None or parsed <= utcnow():
            raise BadRequest("expires_at must be in the future")
        expires_at = iso(parsed)
    secret = KEY_PREFIX + new_opaque_token(32)
    async with connect(ctx.db_path, immediate=True) as db:
        row = await repo.create(
            db,
            user_id=principal.user_id,
            name=data.name,
            prefix=secret[:8],
            key_hash=sha256_hex(secret),
            scopes=data.scopes,
            expires_at=expires_at,
            now=now_iso(),
        )
        await audit.add(db, principal.actor, "apikey.created", target=data.name, details={"scopes": data.scopes, "prefix": secret[:8]})
    return {**_response(row), "key": secret}


async def revoke_key(ctx: AppContext, principal: Principal, key_id: int) -> None:
    async with connect(ctx.db_path, immediate=True) as db:
        row = await repo.get(db, key_id)
        if row is None or (row["user_id"] != principal.user_id and principal.role != "admin"):
            raise NotFound("API key not found")
        await repo.revoke(db, key_id, now_iso())
        await audit.add(db, principal.actor, "apikey.revoked", target=row["name"], details={"prefix": row["prefix"]})


async def authenticate(ctx: AppContext, secret: str, ip: str | None) -> Principal | None:
    """Resolve a bearer/X-API-Key value into a principal, or None."""
    if not secret.startswith(KEY_PREFIX):
        return None
    async with connect(ctx.db_path) as db:
        row = await repo.get_by_hash(db, sha256_hex(secret))
        if row is None or row["revoked_at"]:
            return None
        now = utcnow()
        if row["expires_at"] and (parse_iso(row["expires_at"]) or now) <= now:
            return None
        user = await users_repo.get(db, row["user_id"])
        if user is None or not user["is_active"]:
            return None
        await repo.touch(db, row["id"], iso(now))
    # A key can never exceed its owner's current role.
    scopes = [s for s in row["scopes"] if ROLE_RANK[user["role"]] >= ROLE_RANK[SCOPE_MIN_ROLE.get(s, "admin")]]
    return Principal(user=user, kind="api_key", ip=ip, api_key_id=row["id"], api_key_name=row["name"], scopes=scopes)
