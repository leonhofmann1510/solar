"""
Encryption utilities for sensitive data at rest.

Uses Fernet symmetric encryption with the ENCRYPTION_KEY from settings.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Get the Fernet cipher instance (cached)."""
    return Fernet(settings.encryption_key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    if not plaintext:
        return ""
    cipher = _get_cipher()
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str | None:
    """Decrypt a string value. Returns None if decryption fails."""
    if not ciphertext:
        return None
    try:
        cipher = _get_cipher()
        return cipher.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.warning("Failed to decrypt value - invalid token or wrong key")
        return None
    except Exception as e:
        logger.warning("Decryption error: %s", e)
        return None
