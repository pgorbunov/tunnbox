"""WireGuard key generation with X25519 (no subprocess).

Keys are 32 raw bytes, base64 encoded, exactly like `wg genkey` / `wg pubkey`.
"""

from __future__ import annotations

import base64
import binascii
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def _clamp(raw: bytes) -> bytes:
    data = bytearray(raw)
    data[0] &= 248
    data[31] &= 127
    data[31] |= 64
    return bytes(data)


def generate_private_key() -> str:
    """Return a clamped X25519 private key, base64 encoded."""
    return base64.b64encode(_clamp(secrets.token_bytes(32))).decode()


def public_key_from_private(private_key_b64: str) -> str:
    raw = decode_key(private_key_b64)
    public = X25519PrivateKey.from_private_bytes(raw).public_key()
    return base64.b64encode(
        public.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    ).decode()


def generate_keypair() -> tuple[str, str]:
    """(private, public) base64 pair."""
    private = generate_private_key()
    return private, public_key_from_private(private)


def generate_preshared_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def decode_key(value: str) -> bytes:
    """Decode and validate a base64 WireGuard key (must be 32 bytes)."""
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid WireGuard key encoding") from exc
    if len(raw) != 32:
        raise ValueError("WireGuard keys must be 32 bytes")
    return raw


def is_valid_key(value: str) -> bool:
    try:
        decode_key(value)
    except ValueError:
        return False
    return True
