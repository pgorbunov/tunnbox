"""TOTP multi-factor authentication and recovery codes.

Replay protection: each TOTP step may be accepted once (`users.totp_last_step`),
recovery codes are spent with a conditional UPDATE, and the MFA login token
carries a single-use `jti` (see `auth.login_mfa`).
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite
import qrcode
import qrcode.image.svg

from app.context import AppContext
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.security import (
    generate_recovery_codes,
    hash_recovery_codes_async,
    looks_like_recovery_code,
    match_totp_step,
    new_totp_secret,
    now_iso,
    totp_uri,
    verify_password_async,
    verify_recovery_code_async,
)
from app.db.connection import connect
from app.db.repos import sessions as sessions_repo
from app.db.repos import users as users_repo
from app.services import audit

logger = logging.getLogger(__name__)


def _qr_svg(data: str) -> str:
    image = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return image.to_string(encoding="unicode")


async def _verify_totp_once(ctx: AppContext, db: aiosqlite.Connection, user: dict[str, Any], code: str) -> bool:
    """Accept a code only for a time step newer than the last accepted one."""
    step = match_totp_step(ctx.secrets.decrypt(user["totp_secret_enc"]), code)
    if step is None:
        return False
    last = user.get("totp_last_step")
    if last is not None and step <= int(last):
        return False
    cur = await db.execute(
        "UPDATE users SET totp_last_step = ? WHERE id = ? AND (totp_last_step IS NULL OR totp_last_step < ?)",
        (step, user["id"], step),
    )
    return (cur.rowcount or 0) == 1


async def verify_mfa_code(ctx: AppContext, db: aiosqlite.Connection, user: dict[str, Any], code: str) -> bool:
    """Accept a 6-digit TOTP (once per step) or an unused recovery code (spent atomically)."""
    if not user["totp_secret_enc"]:
        return False
    if looks_like_recovery_code(code):
        for entry in await users_repo.unused_recovery_codes(db, user["id"]):
            if await verify_recovery_code_async(code, entry["code_hash"]):
                return await users_repo.spend_recovery_code(db, entry["id"], now_iso())
        return False
    return await _verify_totp_once(ctx, db, user, code)


async def _issue_recovery_codes(ctx: AppContext, db: aiosqlite.Connection, user_id: int) -> list[str]:
    codes = generate_recovery_codes(10)
    await users_repo.replace_recovery_codes(db, user_id, await hash_recovery_codes_async(codes, ctx.settings.bcrypt_rounds))
    return codes


async def _load_and_check_password(ctx: AppContext, principal: Any, password: str) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
    assert user is not None
    if not await verify_password_async(password, user["password_hash"], ctx.dummy_hash):
        raise Forbidden("Password is incorrect")
    return user


async def setup(ctx: AppContext, principal: Any, password: str) -> dict[str, str]:
    """Create a pending secret (stored encrypted, not yet enabled). Requires the current password."""
    user = await _load_and_check_password(ctx, principal, password)
    if user["totp_enabled"]:
        raise Conflict("MFA is already enabled")
    secret = new_totp_secret()
    async with connect(ctx.db_path, immediate=True) as db:
        await users_repo.update_fields(db, user["id"], now_iso(), totp_secret_enc=ctx.secrets.encrypt(secret), totp_last_step=None)
    uri = totp_uri(secret, user["username"])
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": _qr_svg(uri)}


async def enable(ctx: AppContext, principal: Any, password: str, code: str) -> list[str]:
    await _load_and_check_password(ctx, principal, password)
    async with connect(ctx.db_path, immediate=True) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if user["totp_enabled"]:
            raise Conflict("MFA is already enabled")
        if not user["totp_secret_enc"]:
            raise BadRequest("Run MFA setup first")
        if not await _verify_totp_once(ctx, db, user, code):
            raise BadRequest("Invalid verification code", code="invalid_code")
        await users_repo.update_fields(db, user["id"], now_iso(), totp_enabled=1)
        codes = await _issue_recovery_codes(ctx, db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_enabled", target=user["username"])
        return codes


async def disable(ctx: AppContext, principal: Any, password: str, code: str) -> None:
    await _load_and_check_password(ctx, principal, password)
    async with connect(ctx.db_path, immediate=True) as db:
        user = await users_repo.get(db, principal.user_id)
        assert user is not None
        if not user["totp_enabled"]:
            raise BadRequest("MFA is not enabled")
        if not await verify_mfa_code(ctx, db, user, code):
            raise BadRequest("Invalid verification code", code="invalid_code")
        await _clear(db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_disabled", target=user["username"])


async def regenerate_recovery_codes(ctx: AppContext, principal: Any, password: str) -> list[str]:
    user = await _load_and_check_password(ctx, principal, password)
    if not user["totp_enabled"]:
        raise BadRequest("MFA is not enabled")
    async with connect(ctx.db_path, immediate=True) as db:
        codes = await _issue_recovery_codes(ctx, db, user["id"])
        await audit.add(db, principal.actor, "auth.mfa_enabled", target=user["username"], details={"recovery_codes": "regenerated"})
        return codes


async def _clear(db: aiosqlite.Connection, user_id: int) -> None:
    await users_repo.update_fields(db, user_id, now_iso(), totp_enabled=0, totp_secret_enc=None, totp_last_step=None)
    await users_repo.clear_recovery_codes(db, user_id)


async def admin_reset(ctx: AppContext, actor: audit.Actor, user_id: int) -> None:
    """Clear a user's MFA and revoke their sessions (they must sign in again)."""
    async with connect(ctx.db_path, immediate=True) as db:
        user = await users_repo.get(db, user_id)
        if user is None:
            raise NotFound("User not found")
        await _clear(db, user_id)
        await sessions_repo.revoke_all_for_user(db, user_id, now_iso())
        await audit.add(db, actor, "auth.mfa_disabled", target=user["username"], details={"by_admin": True})
