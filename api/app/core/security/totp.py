"""TOTP (RFC 6238) and recovery codes."""

from __future__ import annotations

import secrets
import time

import pyotp

from app.core.security.tokens import hash_secret

ISSUER = "CompanyMgmt"
RECOVERY_CODES = 10


def new_secret() -> str:
    return str(pyotp.random_base32())


def provisioning_uri(secret: str, account: str) -> str:
    return str(pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER))


def verify(secret: str, code: str, *, last_step: int | None) -> int | None:
    """Check a 6-digit code with ±1 step of drift. Returns the matched time step, or None.

    A step at or before `last_step` is refused, so a code can't be replayed.
    """
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(time.time()) // totp.interval
    for step in (now_step - 1, now_step, now_step + 1):
        if last_step is not None and step <= last_step:
            continue
        if secrets.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def new_recovery_codes() -> list[str]:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return [
        "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(2))
        for _ in range(RECOVERY_CODES)
    ]


def hash_recovery_code(code: str) -> str:
    return hash_secret(code.strip().lower().replace(" ", ""))
