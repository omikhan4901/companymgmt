"""Fixed-window rate limits stored in Postgres (an UNLOGGED table, so no WAL cost).

Counters are written in their own short transaction, so they count even when the request
that hit them fails and rolls back (a failed login must still count).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import open_session
from app.core.errors import TooManyRequests
from app.core.models import Base


class RateLimit(Base):
    __tablename__ = "rate_limits"
    __table_args__ = {"prefixes": ["UNLOGGED"]}

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer)


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int
    window_seconds: int


# Named rules, so limits are easy to find and tune.
LOGIN_IP = Rule("login-ip", 30, 300)
LOGIN_ACCOUNT = Rule("login-account", 10, 900)
SIGNUP_IP = Rule("signup-ip", get_settings().signup_limit_per_hour, 3600)
RESET_IP = Rule("reset-ip", 10, 3600)
RESET_ACCOUNT = Rule("reset-account", 3, 3600)
MFA_SESSION = Rule("mfa", 10, 900)
REFRESH_IP = Rule("refresh-ip", 120, 60)
INVITE_TENANT = Rule("invite-tenant", 100, 3600)
WRITE_USER = Rule("write-user", 600, 60)


_SQL = text(
    """
    INSERT INTO rate_limits (key, window_start, count) VALUES (:key, now(), 1)
    ON CONFLICT (key) DO UPDATE SET
      count = CASE WHEN rate_limits.window_start <= now() - make_interval(secs => :win)
                   THEN 1 ELSE rate_limits.count + 1 END,
      window_start = CASE WHEN rate_limits.window_start <= now() - make_interval(secs => :win)
                   THEN now() ELSE rate_limits.window_start END
    RETURNING count, GREATEST(0, CEIL(EXTRACT(EPOCH FROM
      (rate_limits.window_start + make_interval(secs => :win) - now()))))::int AS retry
    """
)


async def hit(rule: Rule, subject: str) -> tuple[bool, int, int]:
    """Count one hit. Returns (allowed, count, retry_after_seconds)."""
    async with open_session() as db:
        row = (
            await db.execute(_SQL, {"key": f"{rule.name}:{subject}"[:200], "win": rule.window_seconds})
        ).one()
        await db.commit()
    count, retry = int(row[0]), int(row[1])
    return count <= rule.limit, count, retry


async def peek(rule: Rule, subject: str) -> int:
    async with open_session() as db:
        row = (
            await db.execute(
                text(
                    "SELECT count FROM rate_limits WHERE key = :key "
                    "AND window_start > now() - make_interval(secs => :win)"
                ),
                {"key": f"{rule.name}:{subject}"[:200], "win": rule.window_seconds},
            )
        ).first()
    return int(row[0]) if row else 0


async def enforce(rule: Rule, subject: str) -> int:
    allowed, count, retry = await hit(rule, subject)
    if not allowed:
        raise TooManyRequests(headers={"Retry-After": str(max(retry, 1))})
    return count


async def reset(rule: Rule, subject: str) -> None:
    async with open_session() as db:
        await db.execute(
            text("DELETE FROM rate_limits WHERE key = :key"), {"key": f"{rule.name}:{subject}"[:200]}
        )
        await db.commit()
