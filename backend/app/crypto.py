"""Cryptographic utilities for securing sensitive data."""
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging
import os

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def get_encryption_key(salt: bytes) -> bytes:
    """Derive Fernet key from SECRET_KEY with given salt.

    Args:
        salt: Random salt (16+ bytes) for key derivation.

    Returns:
        Fernet-compatible encryption key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return key


def _get_legacy_encryption_key() -> bytes:
    """Derive Fernet key using legacy static salt (for backward compatibility).

    This is only used to decrypt old keys that were encrypted with the static salt.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"wg-ui-static-salt",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return key


def encrypt_private_key(private_key: str) -> str:
    """Encrypt a private key for storage.

    Format: base64(salt):base64(ciphertext)
    where salt is 16 random bytes used for PBKDF2 key derivation.
    """
    if not private_key:
        return private_key

    # Generate random salt (16 bytes)
    salt = os.urandom(16)

    # Derive encryption key with random salt
    f = Fernet(get_encryption_key(salt))
    ciphertext = f.encrypt(private_key.encode())

    # Store salt:ciphertext format
    salt_b64 = base64.urlsafe_b64encode(salt).decode()
    ciphertext_b64 = ciphertext.decode()

    return f"{salt_b64}:{ciphertext_b64}"


def decrypt_private_key(encrypted_key: str) -> str:
    """Decrypt a private key from storage.

    Supports both new format (salt:ciphertext) and legacy format (ciphertext only)
    for backward compatibility.

    Raises:
        ValueError: If the key is not properly encrypted or decryption fails.
    """
    if not encrypted_key:
        return encrypted_key

    # Check if new format (contains colon separator)
    if ":" in encrypted_key:
        try:
            salt_b64, ciphertext_b64 = encrypted_key.split(":", 1)
            salt = base64.urlsafe_b64decode(salt_b64.encode())
            ciphertext = ciphertext_b64.encode()

            f = Fernet(get_encryption_key(salt))
            return f.decrypt(ciphertext).decode()
        except (ValueError, InvalidToken) as e:
            logger.error(f"Failed to decrypt private key with new format: {e}")
            raise ValueError(
                "Failed to decrypt private key. The key may be corrupted or encrypted "
                "with a different SECRET_KEY. Please check your configuration."
            )
    else:
        # Legacy format - try decrypting with static salt
        try:
            f = Fernet(_get_legacy_encryption_key())
            decrypted = f.decrypt(encrypted_key.encode()).decode()

            # Successfully decrypted legacy key - log warning
            logger.warning(
                "Decrypted private key using legacy static salt. "
                "Consider re-encrypting with new format for improved security."
            )
            return decrypted
        except InvalidToken:
            logger.error("Failed to decrypt private key: Invalid token or corrupted data")
            raise ValueError(
                "Failed to decrypt private key. The key may be corrupted or encrypted "
                "with a different SECRET_KEY. Please check your configuration."
            )
        except Exception as e:
            logger.error(f"Unexpected error during key decryption: {e}")
            raise ValueError(f"Failed to decrypt private key: {str(e)}")
