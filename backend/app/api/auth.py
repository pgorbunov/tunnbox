"""/api/auth — setup, login, MFA step, refresh, logout, me, password."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    REFRESH_COOKIE,
    Ctx,
    SessionPrincipal,
    clear_refresh_cookie,
    client_ip,
    optional_principal,
    rate_limit,
    set_refresh_cookie,
)
from app.core.errors import Forbidden
from app.schemas.auth import (
    AuthStatus,
    LoginRequest,
    LoginSuccess,
    MfaLoginRequest,
    MfaRequired,
    PasswordChange,
    RefreshResponse,
    SetupRequest,
)
from app.schemas.users import User
from app.services import auth as auth_service
from app.services.auth import IssuedSession, user_response

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_response(issued: IssuedSession, request: Request, response: Response) -> LoginSuccess:
    set_refresh_cookie(response, request, issued.refresh_token)
    return LoginSuccess(access_token=issued.access_token, expires_in=issued.expires_in, user=User(**issued.user))


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


@router.get("/status", response_model=AuthStatus)
async def auth_status(ctx: Ctx) -> AuthStatus:
    return AuthStatus(**await auth_service.status(ctx))


@router.post("/setup", response_model=LoginSuccess, dependencies=[Depends(rate_limit("login"))])
async def setup(body: SetupRequest, request: Request, response: Response, ctx: Ctx) -> LoginSuccess:
    issued = await auth_service.setup(ctx, body.username, body.password, client_ip(request), _user_agent(request))
    return _login_response(issued, request, response)


@router.post("/login", response_model=LoginSuccess | MfaRequired, dependencies=[Depends(rate_limit("login"))])
async def login(body: LoginRequest, request: Request, response: Response, ctx: Ctx) -> LoginSuccess | MfaRequired:
    result = await auth_service.login(ctx, body.username, body.password, client_ip(request), _user_agent(request))
    if isinstance(result, str):
        return MfaRequired(mfa_token=result)
    return _login_response(result, request, response)


@router.post("/login/mfa", response_model=LoginSuccess, dependencies=[Depends(rate_limit("login"))])
async def login_mfa(body: MfaLoginRequest, request: Request, response: Response, ctx: Ctx) -> LoginSuccess:
    issued = await auth_service.login_mfa(ctx, body.mfa_token, body.code, client_ip(request), _user_agent(request))
    return _login_response(issued, request, response)


def _check_origin(request: Request) -> None:
    """CSRF defence for the cookie-authenticated refresh: Origin/Referer host must match Host."""
    host = request.headers.get("host", "")
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if not value or value == "null":
            if value == "null":
                raise Forbidden("Cross-origin request rejected")
            continue
        if urlsplit(value).netloc.lower() != host.lower():
            raise Forbidden("Cross-origin request rejected")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, response: Response, ctx: Ctx) -> RefreshResponse:
    _check_origin(request)
    token = request.cookies.get(REFRESH_COOKIE)
    try:
        issued = await auth_service.refresh(ctx, token, client_ip(request), _user_agent(request))
    except Exception:
        clear_refresh_cookie(response, request)
        raise
    set_refresh_cookie(response, request, issued.refresh_token)
    return RefreshResponse(access_token=issued.access_token, expires_in=issued.expires_in, user=User(**issued.user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, ctx: Ctx) -> Response:
    principal = await optional_principal(request)
    await auth_service.logout(ctx, principal, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response, request)
    return response


@router.get("/me", response_model=User)
async def me(principal: SessionPrincipal) -> User:
    return User(**user_response(principal.user))


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChange, principal: SessionPrincipal, ctx: Ctx) -> Response:
    await auth_service.change_password(ctx, principal, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
