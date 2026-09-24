"""Password hashing, JWTs, opaque tokens, TOTP and recovery codes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import pyotp
from jose import JWTError, jwt

JWT_ALGORITHM = "HS256"
RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

# Verified against for unknown usernames so login timing does not leak existence.
DUMMY_HASH = bcrypt.hashpw(b"tunnbox-dummy-password", bcrypt.gensalt(rounds=12)).decode()

WORST_PASSWORDS = frozenset(
    {
        "123456", "password", "12345678", "qwerty", "123456789", "12345", "1234", "111111", "1234567",
        "dragon", "123123", "baseball", "abc123", "football", "monkey", "letmein", "shadow", "master",
        "696969", "mustang", "666666", "qwertyuiop", "123321", "1234567890", "pussy", "superman",
        "654321", "1qaz2wsx", "7777777", "fuckyou", "qazwsx", "jordan", "123qwe", "000000", "killer",
        "trustno1", "hunter", "harley", "zxcvbnm", "asdfgh", "buster", "batman", "soccer", "tigger",
        "charlie", "sunshine", "iloveyou", "starwars", "princess", "welcome", "admin", "administrator",
        "password1", "password123", "passw0rd", "p@ssw0rd", "changeme", "wireguard", "tunnbox", "letmein1",
        "qwerty123", "1q2w3e4r", "adminadmin", "root", "toor", "secret", "abcd1234", "welcome1",
    }
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """ISO-8601 UTC with `Z` suffix and no microseconds."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    return iso(utcnow())


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --- Passwords ---------------------------------------------------------------


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time-ish verify; unknown users are checked against DUMMY_HASH."""
    target = password_hash or DUMMY_HASH
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), target.encode())
    except ValueError:
        ok = False
    return ok and password_hash is not None


def validate_password_policy(password: str, username: str) -> str | None:
    """Return an error message if the password violates policy, else None."""
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if len(password) > 128:
        return "Password must be at most 128 characters"
    if password.lower() == username.lower():
        return "Password must not equal the username"
    if password.lower() in WORST_PASSWORDS:
        return "Password is too common"
    return None


# --- Tokens ------------------------------------------------------------------


def new_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def create_jwt(secret: str, claims: dict[str, Any], expires_in: timedelta, purpose: str) -> str:
    now = utcnow()
    payload = {**claims, "iat": int(now.timestamp()), "exp": int((now + expires_in).timestamp()), "purpose": purpose}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_jwt(secret: str, token: str, purpose: str) -> dict[str, Any] | None:
    """Return claims when the signature, expiry and purpose all check out."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != purpose:
        return None
    return payload


# --- TOTP / recovery codes -----------------------------------------------------


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, username: str, issuer: str = "TunnBox") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(8))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    return code.strip().lower().replace(" ", "")


def hash_recovery_code(code: str, rounds: int = 12) -> str:
    return hash_password(normalize_recovery_code(code), rounds=rounds)


def verify_recovery_code(code: str, code_hash: str) -> bool:
    return verify_password(normalize_recovery_code(code), code_hash)


def looks_like_recovery_code(code: str) -> bool:
    text = normalize_recovery_code(code)
    return len(text) == 9 and text[4] == "-"
