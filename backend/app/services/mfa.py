"""TOTP multi-factor authentication and recovery codes."""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite
import qrcode
import qrcode.image.svg

from app.context import AppContext
from app.core.errors import BadRequest, Conflict, Forbidden
from app.core.security import (
    generate_recovery_codes,
    hash_recovery_code,
    looks_like_recovery_code,
    new_totp_secret,
    now_iso,
    totp_uri,
    verify_password,
    verify_recovery_code,
    verify_totp,
)
from app.db.connection import connect
from app.db.repos import users as users_repo
from app.services import audit

logger = logging.getLogger(__name__)


def _qr_svg(data: str) -> str:
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return image.to_string(encoding="unicode")


async def verify_mfa_code(ctx: AppContext, db: aiosqlite.Connection, user: dict[str, Any], code: str) -> bool:
    """Accept a 6-digit TOTP or an unused recovery code (consumed on success)."""
    if not user["totp_secret_enc"]:
        return False
    if looks_like_recovery_code(code):
        for entry in await users_repo.unused_recovery_codes(db, user["id"]):
            if verify_recovery_code(code, entry["code_hash"]):
                await users_repo.mark_recovery_code_used(db, entry["id"], now_iso())
                return True
        return False
    return verify_totp(ctx.secrets.decrypt(user["totp_secret_enc"]), code)


async def _issue_recovery_codes(ctx: AppContext, db: aiosqlite.Connection, user_id: int) -> list[str]:
    codes = generate_recovery_codes(10)
    await users_repo.replace_recovery_codes(db, user_id, [hash_recovery_code(c, ctx.settings.bcrypt_rounds) for c in codes])
    return codes


async def setup(ctx: AppContext, principal: Any) -> dict[str, str]:
    """Create a pending secret (stored encrypted, not yet enabled)."""
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if user["totp_enabled"]:
            raise Conflict("MFA is already enabled")
        secret = new_totp_secret()
        await users_repo.update_fields(db, user["id"], now_iso(), totp_secret_enc=ctx.secrets.encrypt(secret))
    uri = totp_uri(secret, user["username"])
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": _qr_svg(uri)}


async def enable(ctx: AppContext, principal: Any, code: str) -> list[str]:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if user["totp_enabled"]:
            raise Conflict("MFA is already enabled")
        if not user["totp_secret_enc"]:
            raise BadRequest("Run MFA setup first")
        if not verify_totp(ctx.secrets.decrypt(user["totp_secret_enc"]), code):
            raise BadRequest("Invalid verification code", code="invalid_code")
        await users_repo.update_fields(db, user["id"], now_iso(), totp_enabled=1)
        codes = await _issue_recovery_codes(ctx, db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_enabled", target=user["username"])
        return codes


async def disable(ctx: AppContext, principal: Any, password: str, code: str) -> None:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if not verify_password(password, user["password_hash"]):
            raise Forbidden("Password is incorrect")
        if not user["totp_enabled"]:
            raise BadRequest("MFA is not enabled")
        if not await verify_mfa_code(ctx, db, user, code):
            raise BadRequest("Invalid verification code", code="invalid_code")
        await _clear(db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_disabled", target=user["username"])


async def regenerate_recovery_codes(ctx: AppContext, principal: Any, password: str) -> list[str]:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if not verify_password(password, user["password_hash"]):
            raise Forbidden("Password is incorrect")
        if not user["totp_enabled"]:
            raise BadRequest("MFA is not enabled")
        codes = await _issue_recovery_codes(ctx, db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_enabled", target=user["username"], details={"recovery_codes": "regenerated"})
        return codes


async def _clear(db: aiosqlite.Connection, user_id: int) -> None:
    await users_repo.update_fields(db, user_id, now_iso(), totp_enabled=0, totp_secret_enc=None)
    await users_repo.clear_recovery_codes(db, user_id)


async def admin_reset(ctx: AppContext, actor: audit.Actor, user_id: int) -> None:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, user_id)
        if user is None:
            from app.core.errors import NotFound

            raise NotFound("User not found")
        await _clear(db, user_id)
        await audit.add(db, actor, "auth.mfa_disabled", target=user["username"], details={"by_admin": True})
