"""Access tokens (EdDSA JWT) and opaque secrets (refresh, reset, invite tokens)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.config import get_settings

ALGORITHM = "EdDSA"
LEEWAY_SECONDS = 30


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    tenant_id: uuid.UUID | None
    issued_at: datetime


@lru_cache(maxsize=1)
def _keys() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    settings = get_settings()
    pem = settings.jwt_private_key.get_secret_value()
    if pem:
        private = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("JWT_PRIVATE_KEY must be an Ed25519 key.")
        public_pem = settings.jwt_public_key
        public = (
            serialization.load_pem_public_key(public_pem.encode()) if public_pem else private.public_key()
        )
        if not isinstance(public, Ed25519PublicKey):
            raise ValueError("JWT_PUBLIC_KEY must be an Ed25519 key.")
        return private, public
    # Dev/test only (production settings refuse to start without keys).
    private = Ed25519PrivateKey.generate()
    return private, private.public_key()


def create_access_token(
    user_id: uuid.UUID, session_id: uuid.UUID, tenant_id: uuid.UUID | None
) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if tenant_id:
        payload["tid"] = str(tenant_id)
    token = jwt.encode(payload, _keys()[0], algorithm=ALGORITHM)
    return token, expires


def decode_access_token(token: str) -> AccessClaims | None:
    settings = get_settings()
    try:
        data = jwt.decode(
            token,
            _keys()[1],
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "sid", "aud", "iss"]},
        )
        if data["iat"] > datetime.now(UTC).timestamp() + LEEWAY_SECONDS:
            return None
        return AccessClaims(
            user_id=uuid.UUID(data["sub"]),
            session_id=uuid.UUID(data["sid"]),
            tenant_id=uuid.UUID(data["tid"]) if data.get("tid") else None,
            issued_at=datetime.fromtimestamp(data["iat"], UTC),
        )
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        return None


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def same_secret(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
