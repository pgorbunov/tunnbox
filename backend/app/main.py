from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import time
import logging
import secrets
import hmac
import hashlib

from app.config import get_settings
from app.database import init_db
from app.routers import auth, interfaces, peers, system, privacy
from app.routers import settings as settings_router

settings = get_settings()
logger = logging.getLogger(__name__)

# CSRF protection (SEC-007)
CSRF_TOKEN_LENGTH = 32
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def verify_csrf_token(cookie_token: str, header_token: str) -> bool:
    """Verify CSRF token using constant-time comparison."""
    if not cookie_token or not header_token:
        return False
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(cookie_token, header_token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()

    # Security warnings
    if settings.rate_limit_enabled and not settings.rate_limit_redis_url:
        logger.warning(
            "Using in-memory rate limiting. For production with multiple workers, "
            "configure RATE_LIMIT_REDIS_URL."
        )

    yield
    # Shutdown


app = FastAPI(
    title="TunnBox",
    description="Modern web interface for managing WireGuard VPN servers",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disabled - use /api/docs instead
    redoc_url=None,  # Disabled - use /api/redoc instead
    openapi_url="/api/openapi.json",  # Public OpenAPI spec (schema only, no data)
)

# Security headers middleware (SEC-005)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Only add HSTS header when accessed via HTTPS
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy
    # Note: Svelte apps require 'unsafe-inline' for styles due to scoped CSS
    # 'unsafe-inline' for scripts removed for better security
    if request.url.path in ["/api/docs", "/api/redoc"]:
        # Relaxed CSP for API documentation
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )
    else:
        # Strict CSP for application
        # Note: Svelte's production build includes inline scripts in index.html
        # Using 'unsafe-inline' for scripts is necessary for the build to work
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # Required for Svelte build
            "style-src 'self' 'unsafe-inline'; "  # Svelte requires this
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        # Only add upgrade-insecure-requests if accessed via HTTPS
        if request.url.scheme == "https":
            csp_policy += " upgrade-insecure-requests;"

        response.headers["Content-Security-Policy"] = csp_policy

    return response

# CSRF validation middleware (SEC-007)
@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    """Validate CSRF tokens on state-changing requests."""
    # Skip CSRF protection entirely if disabled
    if not settings.csrf_protection_enabled:
        response = await call_next(request)
        return response

    # Skip CSRF check for safe methods
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        response = await call_next(request)
        return response

    # Skip CSRF check for API docs and health check
    if request.url.path in ["/api/health", "/api/docs", "/api/redoc", "/api/openapi.json"]:
        response = await call_next(request)
        return response

    # Skip CSRF check for initial login and setup (no token available yet)
    if request.url.path in ["/api/auth/login", "/api/auth/setup"]:
        response = await call_next(request)
        # Set CSRF token cookie on successful login/setup
        if response.status_code == 200:
            csrf_token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=csrf_token,
                httponly=False,  # Must be readable by JavaScript
                secure=not settings.debug,  # HTTPS only in production
                samesite="strict",
                max_age=86400  # 24 hours
            )
        return response

    # Validate CSRF token for all other state-changing requests
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not verify_csrf_token(cookie_token or "", header_token or ""):
        logger.warning(f"CSRF validation failed for {request.method} {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF validation failed"}
        )

    response = await call_next(request)
    return response


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# CORS middleware (SEC-017)
# Allow CORS_ORIGINS from environment variable (comma-separated)
cors_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "X-CSRF-Token"],
)

# Exception handler for better error messages
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.debug:
        import traceback
        traceback.print_exc()
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# API routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(interfaces.router, prefix="/api/interfaces", tags=["Interfaces"])
app.include_router(peers.router, prefix="/api/interfaces", tags=["Peers"])
app.include_router(settings_router.router)
app.include_router(privacy.router, prefix="/api/privacy", tags=["Privacy"])
app.include_router(system.router, tags=["System"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/docs", include_in_schema=False)
async def get_swagger_ui(request: Request):
    """Public Swagger UI."""
    from fastapi.openapi.docs import get_swagger_ui_html
    
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title=f"{app.title} - API Documentation",
        swagger_favicon_url="/favicon.ico",
    )


@app.get("/api/redoc", include_in_schema=False)
async def get_redoc(request: Request):
    """Public ReDoc."""
    from fastapi.openapi.docs import get_redoc_html
    
    return get_redoc_html(
        openapi_url="/api/openapi.json",
        title=f"{app.title} - API Documentation",
        redoc_favicon_url="/favicon.ico",
    )


@app.post("/api/qr-image")
async def get_qr_image(request: Request):
    """Get QR code image using a signed token in request body (not in URL)."""
    from app.dependencies import validate_qr_token
    from app.database import get_peer_metadata
    from app.services.wireguard import get_wireguard_service
    from app.services.qr_generator import QRGenerator
    from fastapi.responses import Response

    body = await request.json()
    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")

    # Validate token and extract payload
    payload = validate_qr_token(token)
    interface_name = payload["interface_name"]
    public_key = payload["public_key"]

    # Get metadata
    metadata = await get_peer_metadata(interface_name, public_key)
    if not metadata or not metadata.get("private_key"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer configuration not available.",
        )

    # Generate config and QR code
    wg_service = get_wireguard_service()
    try:
        config = await wg_service.generate_client_config(
            interface_name,
            public_key,
            metadata["private_key"],
        )

        qr_image = QRGenerator.generate_qr_code(config)

        return Response(
            content=qr_image,
            media_type="image/png",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# Serve static files in production
static_path = Path(__file__).parent.parent.parent / "frontend" / "build"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(static_path / "index.html")

