"""Field-level encryption (AES-256-GCM) with key ids so keys can rotate."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_PREFIX = "enc1"


def encrypt(plaintext: str, *, context: str) -> str:
    """Encrypt a value. `context` (e.g. "user:<id>:totp") is bound as associated data,
    so a ciphertext copied to another row or field won't decrypt."""
    settings = get_settings()
    kid = settings.field_encryption_active_kid
    key = settings.encryption_keys()[kid]
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), context.encode())
    return f"{_PREFIX}:{kid}:{base64.urlsafe_b64encode(nonce + ct).decode()}"


def decrypt(token: str, *, context: str) -> str:
    prefix, kid, payload = token.split(":", 2)
    if prefix != _PREFIX:
        raise ValueError("Unknown ciphertext format.")
    key = get_settings().encryption_keys()[kid]
    raw = base64.urlsafe_b64decode(payload)
    return AESGCM(key).decrypt(raw[:12], raw[12:], context.encode()).decode()
