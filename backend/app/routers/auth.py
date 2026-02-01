from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta

from app.config import get_settings
from app.dependencies import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    get_current_user,
)
from app.database import (
    get_user_by_username,
    create_user,
    get_user_count,
    save_refresh_token,
    get_refresh_token,
    delete_refresh_token,
    delete_expired_tokens,
    add_audit_log,
    update_user_password,
)
from app.models.user import Token, UserCreate, UserResponse

router = APIRouter()
settings = get_settings()

# Simple in-memory rate limiting (in production, use Redis)
login_attempts: dict[str, list[datetime]] = {}


def get_client_ip(request: Request) -> str:
    """Get client IP with proxy support."""
    # Check if we should trust X-Forwarded-For
    if settings.trusted_proxies:
        trusted = [ip.strip() for ip in settings.trusted_proxies.split(",")]
        client_ip = request.client.host if request.client else "unknown"

        if client_ip in trusted and "x-forwarded-for" in request.headers:
            # Get the first (original client) IP from X-Forwarded-For
            forwarded = request.headers["x-forwarded-for"]
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> bool:
    """Check if IP has exceeded rate limit (5 attempts per minute)."""
    now = datetime.utcnow()
    minute_ago = now - timedelta(minutes=1)

    if ip not in login_attempts:
        login_attempts[ip] = []

    # Clean old attempts
    login_attempts[ip] = [t for t in login_attempts[ip] if t > minute_ago]

    if len(login_attempts[ip]) >= 5:
        return False

    login_attempts[ip].append(now)
    return True


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Login and receive access token."""
    client_ip = get_client_ip(request)

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    user = await get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    # Create refresh token
    refresh_token = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    await save_refresh_token(user["id"], refresh_token, expires_at.isoformat())

    # Set refresh token in httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )

    # Log successful login
    await add_audit_log(user["id"], "login", f"Successful login", client_ip)

    return Token(access_token=access_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: UserResponse = Depends(get_current_user),
):
    """Logout and invalidate refresh token."""
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        await delete_refresh_token(refresh_token)

    response.delete_cookie("refresh_token")

    await add_audit_log(
        current_user.id,
        "logout",
        "User logged out",
        request.client.host if request.client else None,
    )

    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request, response: Response):
    """Refresh access token using refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    # Validate refresh token
    token_data = await get_refresh_token(refresh_token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check expiration
    expires_at = datetime.fromisoformat(token_data["expires_at"])
    if expires_at < datetime.utcnow():
        await delete_refresh_token(refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Get user
    user = await get_user_by_username(
        (await get_user_by_id(token_data["user_id"]))["username"]
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Delete old refresh token and create new one (token rotation)
    await delete_refresh_token(refresh_token)

    new_refresh_token = create_refresh_token()
    new_expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    await save_refresh_token(user["id"], new_refresh_token, new_expires_at.isoformat())

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )

    # Create new access token
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user


@router.patch("/password")
async def change_password(
    request: Request,
    password_data: dict,
    current_user: UserResponse = Depends(get_current_user),
):
    """Change user password."""
    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password and new password are required",
        )

    # Validate new password strength
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long",
        )

    # Get user from database to verify current password
    user = await get_user_by_username(current_user.username)
    if not user or not verify_password(current_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash and update password
    hashed_password = get_password_hash(new_password)
    await update_user_password(current_user.id, hashed_password)

    # Log password change
    client_ip = get_client_ip(request)
    await add_audit_log(
        current_user.id,
        "password_change",
        "Password changed successfully",
        client_ip,
    )

    return {"message": "Password changed successfully"}


@router.post("/setup", response_model=UserResponse)
async def setup_admin(user_data: UserCreate):
    """First-run setup to create admin account. Only works if no users exist."""
    user_count = await get_user_count()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already completed. Admin account exists.",
        )

    # Validate password strength
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    # Create admin user
    hashed_password = get_password_hash(user_data.password)
    await create_user(user_data.username, hashed_password, is_admin=True)

    user = await get_user_by_username(user_data.username)
    return UserResponse(id=user["id"], username=user["username"], is_admin=user["is_admin"])


@router.get("/check-setup")
async def check_setup():
    """Check if initial setup is required."""
    user_count = await get_user_count()
    return {"setup_required": user_count == 0}


# Helper function to get user by ID
async def get_user_by_id(user_id: int):
    import aiosqlite
    from app.database import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
