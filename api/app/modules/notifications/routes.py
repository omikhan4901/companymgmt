"""Notifications API: the signed-in person's own inbox. Everyone has one."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.modules.notifications import service, subscribers  # noqa: F401  (registers subscribers)
from app.modules.notifications.digest import send_digests
from app.modules.notifications.schemas import InboxOut, UnreadOut
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.internal import internal_only

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("", response_model=InboxOut)
async def inbox(
    ctx: Ctx = Depends(allow(None)),
    unread: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> InboxOut:
    return await service.inbox(ctx, unread_only=unread, cursor=cursor, limit=limit)


@router.get("/unread", response_model=UnreadOut)
async def unread(ctx: Ctx = Depends(allow(None))) -> UnreadOut:
    return UnreadOut(unread=await service.unread_count(ctx))


@router.post("/{notification_id}/read", status_code=204)
async def read(notification_id: uuid.UUID, ctx: Ctx = Depends(allow(None))) -> Response:
    await service.mark_read(ctx, notification_id)
    return Response(status_code=204)


@router.post("/read-all", response_model=UnreadOut)
async def read_all(ctx: Ctx = Depends(allow(None))) -> UnreadOut:
    await service.mark_all_read(ctx)
    return UnreadOut(unread=0)


# Called by Cloud Scheduler once a day with the internal token (see runbooks/deploy.md).
internal_router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@internal_router.post("/notifications/digest")
async def digest(_: None = Depends(internal_only)) -> dict[str, int]:
    return {"emails": await send_digests()}
