"""Password hashing (argon2id) and password rules."""

from __future__ import annotations

import gzip
import unicodedata
from functools import lru_cache
from importlib import resources

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 8
MAX_LENGTH = 128

# OWASP guidance for argon2id: m=19 MiB, t=2, p=1 is the minimum. We go a little above.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024 + 5 * 1024, parallelism=1)

# Used to spend the same time when an account doesn't exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


def normalize(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


@lru_cache(maxsize=1)
def _common() -> frozenset[str]:
    data = resources.files("app.core.security").joinpath("data/common-passwords.txt.gz")
    with data.open("rb") as raw, gzip.open(raw, "rt", encoding="utf-8") as f:
        return frozenset(line.strip() for line in f if line.strip())


def problems(password: str, *, context: tuple[str, ...] = ()) -> list[str]:
    """Reasons a new password is not acceptable. Empty list means it's fine."""
    pw = normalize(password)
    issues: list[str] = []
    if len(pw) < MIN_LENGTH:
        issues.append(f"Use at least {MIN_LENGTH} characters.")
    if len(pw) > MAX_LENGTH:
        issues.append(f"Use at most {MAX_LENGTH} characters.")
    lowered = pw.lower()
    if lowered in _common():
        issues.append("This password is too common. Choose something harder to guess.")
    for word in context:
        word = word.strip().lower()
        if len(word) >= 4 and word in lowered:
            issues.append("Don't use your name, email or business name in the password.")
            break
    return issues


def hash_password(password: str) -> str:
    return _hasher.hash(normalize(password))


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, normalize(password)) and bool(stored_hash)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
