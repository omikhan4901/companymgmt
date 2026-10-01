"""Notification capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.notifications import service
from app.modules.notifications.schemas import InboxOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class InboxIn(BaseModel):
    unread: bool = Field(default=False, description="Only the ones not read yet")
    limit: int = Field(default=20, ge=1, le=100)


@capability(
    "notifications.inbox",
    "Your latest notifications: requests waiting on you and decisions about your own.",
    input=InboxIn,
    output=InboxOut,
    permission=None,
    module=None,
    route="GET /v1/notifications",
)
async def inbox(ctx: Ctx, data: InboxIn) -> InboxOut:
    return await service.inbox(ctx, unread_only=data.unread, cursor=None, limit=data.limit)
