"""Time helpers. Instants are UTC; calendar days are always in a named timezone."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(UTC)


def local_date(instant: datetime, timezone: str) -> date:
    return instant.astimezone(ZoneInfo(timezone)).date()


def today(timezone: str) -> date:
    return local_date(utcnow(), timezone)
