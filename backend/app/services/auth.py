"""Login flow, sessions, refresh rotation, lockout and password changes.

All mutating paths open the DB with `immediate=True` so counters, lockouts
and token rotation are serialised; bcrypt work runs in a bounded thread pool.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import aiosqlite

from app import __version__
from app.context import AppContext
from app.core.errors import BadRequest, Conflict, Forbidden, Locked, Unauthorized
from app.core.security import (
    create_jwt,
    decode_jwt,
    hash_password_async,
    iso,
    new_opaque_token,
    now_iso,
    parse_iso,
    sha256_hex,
    utcnow,
    validate_password_policy,
    verify_password_async,
)
from app.db.connection import connect
from app.db.repos import api_keys as api_keys_repo
from app.db.repos import sessions as sessions_repo
from app.db.repos import users as users_repo
from app.schemas.common import ROLE_RANK
from app.services import audit
from app.services.mfa import verify_mfa_code

logger = logging.getLogger(__name__)

MFA_TOKEN_TTL = timedelta(minutes=5)
INVALID_CREDENTIALS = "Invalid username or password"


@dataclass
class Principal:
    """An authenticated caller: a user session or an API key."""

    user: dict[str, Any]
    kind: str  # "session" | "api_key"
    ip: str | None = None
    session_id: str | None = None
    api_key_id: int | None = None
    api_key_name: str | None = None
    scopes: list[str] = field(default_factory=list)

    @property
    def user_id(self) -> int:
        return int(self.user["id"])

    @property
    def role(self) -> str:
        return str(self.user["role"])

    @property
    def is_session(self) -> bool:
        return self.kind == "session"

    def has_role(self, minimum: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]

    def has_scope(self, scope: str) -> bool:
        if self.is_session:
            return True
        if "admin" in self.scopes:
            return True
        if scope == "read":
            return bool(self.scopes)
        return scope in self.scopes

    @property
    def actor(self) -> audit.Actor:
        username = self.user["username"] if self.is_session else f"api-key:{self.api_key_name}"
        return audit.Actor(user_id=self.user_id, username=username, ip=self.ip)


def user_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "totp_enabled": bool(row["totp_enabled"]),
        "last_login_at": row["last_login_at"],
        "created_at": row["created_at"],
    }


@dataclass
class IssuedSession:
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict[str, Any]
    session_id: str


def _access_token(ctx: AppContext, user: dict[str, Any], session_id: str) -> tuple[str, int]:
    ttl = timedelta(minutes=ctx.settings.access_token_expire_minutes)
    token = create_jwt(
        ctx.settings.secret_key,
        {"sub": str(user["id"]), "sid": session_id, "role": user["role"]},
        ttl,
        purpose="access",
    )
    return token, int(ttl.total_seconds())


async def issue_session(ctx: AppContext, db: aiosqlite.Connection, user: dict[str, Any], ip: str | None, user_agent: str | None) -> IssuedSession:
    now = utcnow()
    session_id = str(uuid.uuid4())
    refresh = new_opaque_token(32)
    await sessions_repo.create(
        db,
        session_id=session_id,
        user_id=user["id"],
        refresh_hash=sha256_hex(refresh),
        ip=ip,
        user_agent=(user_agent or "")[:300] or None,
        now=iso(now),
        expires_at=iso(now + timedelta(days=ctx.settings.refresh_token_expire_days)),
        absolute_expires_at=iso(now + timedelta(days=ctx.settings.session_absolute_days)),
    )
    await users_repo.update_fields(db, user["id"], iso(now), last_login_at=iso(now), failed_logins=0, locked_until=None)
    user = {**user, "last_login_at": iso(now)}
    access, expires_in = _access_token(ctx, user, session_id)
    return IssuedSession(access, refresh, expires_in, user_response(user), session_id)


def _is_locked(user: dict[str, Any]) -> bool:
    locked_until = parse_iso(user.get("locked_until"))
    return locked_until is not None and locked_until > utcnow()


# --- status / setup ----------------------------------------------------------------


async def status(ctx: AppContext) -> dict[str, Any]:
    async with connect(ctx.db_path) as db:
        return {"setup_required": await users_repo.count(db) == 0, "version": __version__}


async def setup(ctx: AppContext, username: str, password: str, ip: str | None, user_agent: str | None) -> IssuedSession:
    error = validate_password_policy(password, username)
    if error:
        raise BadRequest(error, code="weak_password")
    password_hash = await hash_password_async(password, ctx.settings.bcrypt_rounds)
    async with connect(ctx.db_path, immediate=True) as db:  # count + insert are one write txn
        if await users_repo.count(db) > 0:
            raise Conflict("Setup already completed")
        user = await users_repo.create(db, username, password_hash, "admin", now_iso())
        issued = await issue_session(ctx, db, user, ip, user_agent)
        await audit.add(db, audit.Actor(user["id"], user["username"], ip), "auth.setup", target=user["username"])
        return issued


# --- login -----------------------------------------------------------------------


async def login(ctx: AppContext, username: str, password: str, ip: str | None, user_agent: str | None) -> IssuedSession | str:
    """Return an IssuedSession, or an MFA token string when a second factor is required."""
    async with connect(ctx.db_path) as db:
        user = await users_repo.get_by_username(db, username)
    if user and _is_locked(user):
        await verify_password_async(password, None, ctx.dummy_hash)  # burn time like a normal attempt
        raise Locked()
    ok = await verify_password_async(password, user["password_hash"] if user else None, ctx.dummy_hash)
    if not ok or user is None or not user["is_active"]:
        async with connect(ctx.db_path, immediate=True) as db:
            if user is not None:
                await _record_failure(ctx, db, user, ip)
            else:
                await audit.add(db, audit.Actor(None, username[:64], ip), "auth.login_failed", target=username[:64])
        raise Unauthorized(INVALID_CREDENTIALS)
    if user["totp_enabled"]:
        return create_jwt(ctx.settings.secret_key, {"sub": str(user["id"]), "jti": uuid.uuid4().hex}, MFA_TOKEN_TTL, purpose="mfa")
    async with connect(ctx.db_path, immediate=True) as db:
        issued = await issue_session(ctx, db, user, ip, user_agent)
        await audit.add(db, audit.Actor(user["id"], user["username"], ip), "auth.login", target=user["username"])
        return issued


async def _record_failure(ctx: AppContext, db: aiosqlite.Connection, user: dict[str, Any], ip: str | None) -> None:
    """Atomically bump the failure counter and lock the account at the threshold."""
    actor = audit.Actor(user["id"], user["username"], ip)
    await audit.add(db, actor, "auth.login_failed", target=user["username"])
    failures = await users_repo.increment_failed_logins(db, user["id"], now_iso())
    if failures >= ctx.settings.lockout_threshold:
        locked_until = iso(utcnow() + timedelta(minutes=ctx.settings.lockout_minutes))
        await users_repo.update_fields(db, user["id"], now_iso(), failed_logins=0, locked_until=locked_until)
        await audit.add(db, actor, "auth.locked", target=user["username"], details={"until": locked_until})
        logger.warning("Account %s locked after %d failed logins", user["username"], failures)


async def login_mfa(ctx: AppContext, mfa_token: str, code: str, ip: str | None, user_agent: str | None) -> IssuedSession:
    claims = decode_jwt(ctx.settings.secret_key, mfa_token, purpose="mfa")
    if not claims or "jti" not in claims or "sub" not in claims:
        raise Unauthorized("MFA token invalid or expired")
    async with connect(ctx.db_path, immediate=True) as db:
        user = await users_repo.get(db, int(claims["sub"]))
        if user is None or not user["is_active"] or not user["totp_enabled"]:
            raise Unauthorized("MFA token invalid or expired")
        if _is_locked(user):
            raise Locked()
        if not await verify_mfa_code(ctx, db, user, code):
            await _record_failure(ctx, db, user, ip)
            await db.commit()  # keep the bookkeeping despite the error raised next
            raise Unauthorized("Invalid verification code")
        expires_at = iso(utcnow() + MFA_TOKEN_TTL)
        if not await users_repo.consume_mfa_token(db, str(claims["jti"]), expires_at):
            raise Unauthorized("MFA token already used")
        issued = await issue_session(ctx, db, user, ip, user_agent)
        await audit.add(db, audit.Actor(user["id"], user["username"], ip), "auth.login", target=user["username"], details={"mfa": True})
        return issued


# --- refresh / logout --------------------------------------------------------------


async def refresh(ctx: AppContext, refresh_token: str | None, ip: str | None, user_agent: str | None) -> IssuedSession:
    """Rotate the refresh token. Reuse of an already-rotated token revokes the whole session."""
    if not refresh_token:
        raise Unauthorized("No refresh token")
    token_hash = sha256_hex(refresh_token)
    async with connect(ctx.db_path, immediate=True) as db:
        session = await sessions_repo.get_by_refresh_hash(db, token_hash)
        now = utcnow()
        if session is None:
            stolen_session = await sessions_repo.session_id_for_rotated_hash(db, token_hash)
            if stolen_session:
                await _revoke_for_reuse(db, stolen_session, ip, now)
            raise Unauthorized("Invalid refresh token")
        if session["revoked_at"]:
            raise Unauthorized("Invalid refresh token")
        if (parse_iso(session["expires_at"]) or now) <= now or (parse_iso(session["absolute_expires_at"]) or now) <= now:
            await sessions_repo.revoke(db, session["id"], iso(now))
            await db.commit()
            raise Unauthorized("Session expired")
        user = await users_repo.get(db, session["user_id"])
        if user is None or not user["is_active"]:
            await sessions_repo.revoke(db, session["id"], iso(now))
            await db.commit()
            raise Unauthorized("Session expired")
        new_refresh = new_opaque_token(32)
        sliding = now + timedelta(days=ctx.settings.refresh_token_expire_days)
        absolute = parse_iso(session["absolute_expires_at"]) or sliding
        rotated = await sessions_repo.rotate(db, session["id"], token_hash, sha256_hex(new_refresh), iso(now), iso(min(sliding, absolute)))
        if not rotated:  # someone else rotated it between our read and write: treat as reuse
            await _revoke_for_reuse(db, session["id"], ip, now)
            raise Unauthorized("Invalid refresh token")
        access, expires_in = _access_token(ctx, user, session["id"])
        return IssuedSession(access, new_refresh, expires_in, user_response(user), session["id"])


async def _revoke_for_reuse(db: aiosqlite.Connection, session_id: str, ip: str | None, now: Any) -> None:
    await sessions_repo.revoke(db, session_id, iso(now))
    await audit.add(db, audit.Actor(None, "system", ip), "auth.session_revoked", target=session_id, details={"reason": "refresh_token_reuse"})
    await db.commit()
    logger.warning("Refresh token reuse detected; session %s revoked", session_id)


async def logout(ctx: AppContext, principal: Principal | None, refresh_token: str | None) -> None:
    async with connect(ctx.db_path, immediate=True) as db:
        session_id = principal.session_id if principal and principal.is_session else None
        if session_id is None and refresh_token:
            session = await sessions_repo.get_by_refresh_hash(db, sha256_hex(refresh_token))
            session_id = session["id"] if session else None
        if session_id:
            await sessions_repo.revoke(db, session_id, now_iso())
            actor = principal.actor if principal else audit.Actor(None, None, None)
            await audit.add(db, actor, "auth.logout", target=session_id)


# --- principal loading ---------------------------------------------------------------


async def principal_from_access_token(ctx: AppContext, token: str, ip: str | None) -> Principal | None:
    claims = decode_jwt(ctx.settings.secret_key, token, purpose="access")
    if not claims or "sid" not in claims or "sub" not in claims:
        return None
    async with connect(ctx.db_path) as db:
        session = await sessions_repo.get(db, str(claims["sid"]))
        now = utcnow()
        if session is None or session["revoked_at"] or (parse_iso(session["expires_at"]) or now) <= now:
            return None
        user = await users_repo.get(db, int(claims["sub"]))
        if user is None or not user["is_active"] or user["id"] != session["user_id"]:
            return None
        return Principal(user=user, kind="session", ip=ip, session_id=session["id"])


# --- password & sessions -------------------------------------------------------------


async def verify_current_password(ctx: AppContext, user: dict[str, Any], password: str) -> None:
    """Raise 403 unless `password` is the user's current password."""
    if not await verify_password_async(password, user["password_hash"], ctx.dummy_hash):
        raise Forbidden("Password is incorrect")


async def change_password(ctx: AppContext, principal: Principal, current: str, new: str) -> None:
    async with connect(ctx.db_path) as db:
        user = await users_repo.get(db, principal.user_id)
    assert user is not None
    if not await verify_password_async(current, user["password_hash"], ctx.dummy_hash):
        raise Forbidden("Current password is incorrect")
    error = validate_password_policy(new, user["username"])
    if error:
        raise BadRequest(error, code="weak_password")
    password_hash = await hash_password_async(new, ctx.settings.bcrypt_rounds)
    async with connect(ctx.db_path, immediate=True) as db:
        now = now_iso()
        await users_repo.update_fields(db, user["id"], now, password_hash=password_hash, password_changed_at=now)
        await sessions_repo.revoke_all_for_user(db, user["id"], now, except_id=principal.session_id)
        await audit.add(db, principal.actor, "auth.password_changed", target=user["username"])


async def list_sessions(ctx: AppContext, principal: Principal) -> list[dict[str, Any]]:
    async with connect(ctx.db_path) as db:
        rows = await sessions_repo.list_active_for_user(db, principal.user_id, now_iso())
    return [
        {
            "id": r["id"],
            "ip": r["ip"],
            "user_agent": r["user_agent"],
            "created_at": r["created_at"],
            "last_used_at": r["last_used_at"],
            "expires_at": r["expires_at"],
            "current": r["id"] == principal.session_id,
        }
        for r in rows
    ]


async def revoke_session(ctx: AppContext, principal: Principal, session_id: str) -> None:
    async with connect(ctx.db_path, immediate=True) as db:
        session = await sessions_repo.get(db, session_id)
        if session is None or session["user_id"] != principal.user_id:
            raise Forbidden("Session not found")
        await sessions_repo.revoke(db, session_id, now_iso())
        await audit.add(db, principal.actor, "auth.session_revoked", target=session_id)


async def revoke_other_sessions(ctx: AppContext, principal: Principal) -> None:
    async with connect(ctx.db_path, immediate=True) as db:
        count = await sessions_repo.revoke_all_for_user(db, principal.user_id, now_iso(), except_id=principal.session_id)
        await audit.add(db, principal.actor, "auth.session_revoked", target="all", details={"count": count})


async def revoke_everything_for_user(db: aiosqlite.Connection, user_id: int) -> None:
    """Sessions and API keys, e.g. when a user is disabled."""
    now = now_iso()
    await sessions_repo.revoke_all_for_user(db, user_id, now)
    await api_keys_repo.revoke_all_for_user(db, user_id, now)
