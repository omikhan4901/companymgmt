"""Announcements API: the feed, posting, read marks and receipts."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import check_if_match, set_etag
from app.modules.announcements import access, service
from app.modules.announcements.schemas import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementPatch,
    ReceiptsOut,
    UnreadOut,
)
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/announcements", tags=["announcements"])
MODULE = "announcements"
Read = Depends(allow(access.READ, module=MODULE))
Post = Depends(allow(access.POST, module=MODULE))


@router.get("", response_model=list[AnnouncementOut])
async def feed(ctx: Ctx = Read, limit: int = Query(default=30, ge=1, le=100)) -> list[AnnouncementOut]:
    return await service.feed(ctx, limit=limit)


@router.get("/unread", response_model=UnreadOut)
async def unread(ctx: Ctx = Read) -> UnreadOut:
    return UnreadOut(unread=await service.unread_count(ctx))


@router.post("", response_model=AnnouncementOut, status_code=201)
async def create(body: AnnouncementIn, ctx: Ctx = Post) -> AnnouncementOut:
    return await service.create(ctx, body)


@router.get("/{announcement_id}", response_model=AnnouncementOut)
async def get(announcement_id: uuid.UUID, response: Response, ctx: Ctx = Read) -> AnnouncementOut:
    post = await service.get(ctx, announcement_id)
    set_etag(response, post.version)
    return post


@router.patch("/{announcement_id}", response_model=AnnouncementOut)
async def update(
    announcement_id: uuid.UUID, body: AnnouncementPatch, request: Request, response: Response, ctx: Ctx = Post
) -> AnnouncementOut:
    check_if_match(request, (await service.get(ctx, announcement_id)).version)
    post = await service.update(ctx, announcement_id, body)
    set_etag(response, post.version)
    return post


@router.delete("/{announcement_id}", status_code=204)
async def remove(announcement_id: uuid.UUID, ctx: Ctx = Post) -> Response:
    await service.remove(ctx, announcement_id)
    return Response(status_code=204)


@router.post("/{announcement_id}/read", status_code=204)
async def mark_read(announcement_id: uuid.UUID, ctx: Ctx = Read) -> Response:
    await service.mark_read(ctx, announcement_id)
    return Response(status_code=204)


@router.get("/{announcement_id}/receipts", response_model=ReceiptsOut)
async def receipts(announcement_id: uuid.UUID, ctx: Ctx = Post) -> ReceiptsOut:
    return await service.receipts(ctx, announcement_id)
