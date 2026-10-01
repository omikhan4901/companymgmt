"""Announcement capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.announcements import access, service
from app.modules.announcements.schemas import AnnouncementOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class FeedIn(BaseModel):
    limit: int = Field(default=30, ge=1, le=100)


@capability(
    "announcements.feed",
    "Announcements addressed to you, pinned first, then newest.",
    input=FeedIn,
    output=list[AnnouncementOut],
    permission=access.READ,
    module="announcements",
    route="GET /v1/announcements",
)
async def feed(ctx: Ctx, data: FeedIn) -> list[AnnouncementOut]:
    return await service.feed(ctx, limit=data.limit)
