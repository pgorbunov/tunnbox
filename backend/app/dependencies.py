from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from datetime import datetime, timedelta
import secrets

from app.config import get_settings
from app.database import get_user_by_username
from app.models.user import TokenData, UserResponse

settings = get_settings()

# Constants for QR token expiry
QR_TOKEN_EXPIRE_MINUTES = 5

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except ValueError:
        # Handle cases where existing hash might be invalid or incompatible
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def create_qr_token(interface_name: str, public_key: str) -> str:
    """Create a short-lived signed token for QR code access."""
    to_encode = {
        "interface_name": interface_name,
        "public_key": public_key,
        "exp": datetime.utcnow() + timedelta(minutes=QR_TOKEN_EXPIRE_MINUTES)
    }
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def validate_qr_token(token: str) -> dict:
    """Validate QR token and return the payload."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        interface_name = payload.get("interface_name")
        public_key = payload.get("public_key")

        if not interface_name or not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid QR token",
            )

        return {"interface_name": interface_name, "public_key": public_key}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="QR token expired or invalid",
        )


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = await get_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception

    return UserResponse(id=user["id"], username=user["username"], is_admin=user["is_admin"])


async def get_current_admin_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
