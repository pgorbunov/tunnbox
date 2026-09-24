"""Fernet encryption of secrets at rest (v1-compatible format).

Format: `base64url(salt):fernet_token`, where the Fernet key is PBKDF2-SHA256
(100k iterations) of SECRET_KEY with that salt. Values without a `:` are
legacy tokens encrypted with a static salt and remain decryptable.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_LEGACY_SALT = b"wg-ui-static-salt"
_ITERATIONS = 100_000


class DecryptionError(ValueError):
    """Raised when a stored secret cannot be decrypted (wrong SECRET_KEY or corrupt)."""


@lru_cache(maxsize=4096)
def _derive(secret_key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))


class SecretBox:
    """Encrypts and decrypts strings with keys derived from `secret_key`.

    One random salt is drawn per instance (process) so the expensive KDF runs
    once for new values; every previously used salt is cached on decrypt.
    """

    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key
        self._salt = os.urandom(16)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        token = Fernet(_derive(self._secret_key, self._salt)).encrypt(plaintext.encode())
        return f"{base64.urlsafe_b64encode(self._salt).decode()}:{token.decode()}"

    def decrypt(self, stored: str) -> str:
        if not stored:
            return stored
        try:
            if ":" in stored:
                salt_b64, token = stored.split(":", 1)
                salt = base64.urlsafe_b64decode(salt_b64.encode())
                return Fernet(_derive(self._secret_key, salt)).decrypt(token.encode()).decode()
            return Fernet(_derive(self._secret_key, _LEGACY_SALT)).decrypt(stored.encode()).decode()
        except (InvalidToken, ValueError, TypeError) as exc:
            raise DecryptionError(
                "Failed to decrypt stored secret; it may be corrupted or encrypted with a different SECRET_KEY"
            ) from exc
