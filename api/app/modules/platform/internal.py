"""Internal endpoints called by Cloud Scheduler / Cloud Tasks, protected by a shared
secret header (INTERNAL_TOKEN). Not reachable without it."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy import text

from app.core import outbox
from app.core.config import get_settings
from app.core.db import open_session
from app.core.errors import NotFound
from app.core.security.tokens import same_secret

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


async def internal_only(x_internal_token: str | None = Header(default=None)) -> None:
    expected = get_settings().internal_token.get_secret_value()
    if not expected or not x_internal_token or not same_secret(expected, x_internal_token):
        # Look like a missing route to anyone probing.
        raise NotFound()


internal_only._access = "internal"  # type: ignore[attr-defined]


@router.post("/outbox/dispatch")
async def dispatch_outbox(_: None = Depends(internal_only)) -> dict[str, int]:
    return {"delivered": await outbox.dispatch(limit=200)}


@router.post("/maintenance/daily")
async def daily_maintenance(_: None = Depends(internal_only)) -> dict[str, int]:
    """Clean up expired auth rows and delivered outbox events."""
    async with open_session() as db:
        results = {}
        for name, sql in (
            ("refresh_tokens", "DELETE FROM refresh_tokens WHERE expires_at < now() - interval '1 day'"),
            ("challenges", "DELETE FROM auth_challenges WHERE expires_at < now() - interval '1 day'"),
            ("email_tokens", "DELETE FROM email_tokens WHERE expires_at < now() - interval '7 days'"),
            ("outbox", "DELETE FROM outbox_events WHERE dispatched_at < now() - interval '14 days'"),
            ("rate_limits", "DELETE FROM rate_limits WHERE window_start < now() - interval '1 day'"),
        ):
            result = await db.execute(text(sql))
            results[name] = int(getattr(result, "rowcount", 0) or 0)
        await db.commit()
    return results
