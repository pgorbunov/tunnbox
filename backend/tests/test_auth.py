import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dependencies import verify_password, get_password_hash, create_access_token
from app.config import get_settings


def test_password_hashing():
    """Test password hashing and verification."""
    password = "test_password_123"
    hashed = get_password_hash(password)

    # Hash should be different from original
    assert hashed != password

    # Should verify correctly
    assert verify_password(password, hashed) is True

    # Wrong password should not verify
    assert verify_password("wrong_password", hashed) is False


def test_password_hashing_different_each_time():
    """Test that hashing produces different results each time (salt)."""
    password = "test_password_123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    # Hashes should be different due to salt
    assert hash1 != hash2

    # But both should verify
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_create_access_token():
    """Test JWT access token creation."""
    data = {"sub": "testuser", "user_id": 1}
    token = create_access_token(data)

    # Token should be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0

    # Token should have three parts (header.payload.signature)
    parts = token.split('.')
    assert len(parts) == 3


def test_create_access_token_with_expiry():
    """Test JWT token creation with custom expiry."""
    from datetime import timedelta

    data = {"sub": "testuser"}
    token = create_access_token(data, expires_delta=timedelta(minutes=5))

    assert isinstance(token, str)
    assert len(token) > 0


def test_settings():
    """Test settings loading."""
    settings = get_settings()

    # Check default values
    assert settings.app_port == 8000
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes == 15
    assert settings.refresh_token_expire_days == 7
