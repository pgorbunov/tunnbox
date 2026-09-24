"""Request-scoped dependencies: context, client IP, principals, RBAC and scopes."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request, Response

from app.context import AppContext
from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.services import api_keys as api_keys_service
from app.services import auth as auth_service
from app.services.auth import Principal

REFRESH_COOKIE = "tb_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]


def _peer_is_trusted(ctx: AppContext, host: str | None) -> bool:
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for entry in ctx.settings.trusted_proxy_list:
        try:
            if entry == "*" or addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request) -> str | None:
    """Real client IP, honouring X-Forwarded-For only from trusted proxies."""
    ctx = get_ctx(request)
    host = request.client.host if request.client else None
    if _peer_is_trusted(ctx, host):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return host


def request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    ctx = get_ctx(request)
    host = request.client.host if request.client else None
    if _peer_is_trusted(ctx, host):
        return request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https"
    return False


def cookie_secure(request: Request) -> bool:
    mode = get_ctx(request).settings.cookie_secure.lower()
    if mode in {"true", "1", "yes"}:
        return True
    if mode in {"false", "0", "no"}:
        return False
    return request_is_https(request)


def set_refresh_cookie(response: Response, request: Request, token: str) -> None:
    ctx = get_ctx(request)
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=ctx.settings.refresh_token_expire_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=cookie_secure(request),
    )


def clear_refresh_cookie(response: Response, request: Request) -> None:
    response.set_cookie(
        REFRESH_COOKIE, "", max_age=0, expires=0, path=REFRESH_COOKIE_PATH, httponly=True,
        samesite="strict", secure=cookie_secure(request),
    )


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


async def optional_principal(request: Request) -> Principal | None:
    ctx = get_ctx(request)
    ip = client_ip(request)
    api_key = request.headers.get("x-api-key")
    token = _bearer(request)
    if api_key or (token and token.startswith(api_keys_service.KEY_PREFIX)):
        return await api_keys_service.authenticate(ctx, api_key or token or "", ip)
    if token:
        return await auth_service.principal_from_access_token(ctx, token, ip)
    return None


async def get_current_principal(request: Request) -> Principal:
    principal = await optional_principal(request)
    if principal is None:
        raise Unauthorized()
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def session_principal(principal: CurrentPrincipal) -> Principal:
    """Endpoints that API keys may never call."""
    if not principal.is_session:
        raise Forbidden("API keys cannot access this endpoint")
    return principal


SessionPrincipal = Annotated[Principal, Depends(session_principal)]


def require(role: str = "viewer", scope: str = "read") -> Callable[..., Principal]:
    """Dependency factory: minimum role (sessions and keys) plus scope (keys only)."""

    async def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_role(role):
            raise Forbidden()
        if not principal.has_scope(scope):
            raise Forbidden("API key lacks the required scope")
        return principal

    return dependency


def require_role(role: str) -> Callable[..., Principal]:
    return require(role, "admin" if role == "admin" else "read")


def rate_limit(bucket: str, limit: int | None = None, window: int | None = None) -> Callable[..., None]:
    """Per-IP limiter; defaults to LOGIN_RATE_LIMIT."""

    async def dependency(request: Request) -> None:
        ctx = get_ctx(request)
        max_hits, seconds = (limit, window) if limit and window else ctx.settings.login_rate
        allowed, retry_after = ctx.limiter.check(bucket, client_ip(request) or "unknown", max_hits, seconds)
        if not allowed:
            raise RateLimited(retry_after)

    return dependency
