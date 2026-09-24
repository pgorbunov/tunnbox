"""FastAPI application factory: middleware, error handlers, static SPA, lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException  # base class: also raised by StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api.deps import request_is_https
from app.api.router import api_router
from app.config import Settings, get_settings
from app.context import AppContext
from app.core.crypto import SecretBox
from app.core.csp import DOCS_CSP, build_app_csp, inline_script_hashes
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.security import now_iso
from app.db.connection import connect
from app.db.migrations import run_migrations
from app.db.repos import settings as settings_repo
from app.services import interfaces as interfaces_service
from app.services import peers as peers_service
from app.services import stats as stats_service
from app.services.wireguard import get_backend

logger = logging.getLogger(__name__)

FRONTEND_BUILD = Path(__file__).resolve().parent.parent.parent / "frontend" / "build"
DOCS_PATHS = {"/api/docs", "/api/redoc", "/api/docs/oauth2-redirect"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the security headers and CSP from spec §2.4."""

    def __init__(self, app: FastAPI, app_csp: str) -> None:  # type: ignore[override]
        super().__init__(app)
        self.app_csp = app_csp

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
        headers["Cross-Origin-Resource-Policy"] = "same-origin"
        headers["Content-Security-Policy"] = DOCS_CSP if request.url.path in DOCS_PATHS else self.app_csp
        if request_is_https(request):
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


async def _startup(ctx: AppContext) -> None:
    settings = ctx.settings
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    async with connect(settings.db_path) as db:
        await run_migrations(db, now_iso())
        await settings_repo.ensure_defaults(
            db,
            settings_repo.defaults(
                public_endpoint=settings.wg_default_endpoint,
                default_dns=settings.wg_default_dns,
                stats_retention_days=settings.stats_retention_days,
            ),
            now_iso(),
        )
    await interfaces_service.reconcile(ctx)
    scheduler = ctx.scheduler
    scheduler.add_job("stats_sampler", lambda: stats_service.sample(ctx), settings.stats_sample_seconds)
    scheduler.add_job("peer_expiry", lambda: peers_service.expire_peers(ctx), 60)
    scheduler.add_job("retention", lambda: stats_service.retention(ctx), 3600)
    scheduler.start()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_format, settings.debug)
    ctx = AppContext(
        settings=settings,
        backend=get_backend(settings.backend_mode, settings.config_dir),
        secrets=SecretBox(settings.secret_key),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("TunnBox %s starting (backend=%s, db=%s)", __version__, ctx.backend.mode, settings.db_path)
        await _startup(ctx)
        try:
            yield
        finally:
            await ctx.scheduler.stop()

    app = FastAPI(
        title="TunnBox",
        description="Self-hosted WireGuard management",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=settings.debug,
    )
    app.state.ctx = ctx

    app.add_middleware(SecurityHeadersMiddleware, app_csp=build_app_csp(inline_script_hashes(FRONTEND_BUILD / "index.html")))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept"],
    )

    _install_error_handlers(app, settings)
    app.include_router(api_router)
    _mount_frontend(app)
    return app


def _install_error_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code}, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
            messages.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages) or "Validation error", "code": "validation_error"})

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> Response:
        if exc.status_code == 404 and not request.url.path.startswith("/api") and _index_file() is not None:
            return FileResponse(_index_file())  # SPA fallback
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=dict(exc.headers or {}))

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        detail = f"{type(exc).__name__}: {exc}" if settings.debug else "Internal server error"
        return JSONResponse(status_code=500, content={"detail": detail, "code": "internal_error"})


def _index_file() -> Path | None:
    index = FRONTEND_BUILD / "index.html"
    return index if index.is_file() else None


def _mount_frontend(app: FastAPI) -> None:
    if FRONTEND_BUILD.is_dir() and _index_file() is not None:
        app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="frontend")
    else:
        logger.info("Frontend build not found at %s; serving API only", FRONTEND_BUILD)


app = create_app()
