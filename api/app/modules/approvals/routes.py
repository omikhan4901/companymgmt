"""Approvals API: the inbox, its count, and decisions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.modules.approvals import service
from app.modules.approvals.schemas import CountOut, DecisionIn, DecisionOut, InboxOut, Kind
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


@router.get("", response_model=InboxOut)
async def inbox(ctx: Ctx = Depends(allow(None))) -> InboxOut:
    return InboxOut(items=await service.pending(ctx))


@router.get("/count", response_model=CountOut)
async def count(ctx: Ctx = Depends(allow(None))) -> CountOut:
    return CountOut(count=len(await service.pending(ctx)))


@router.post("/{kind}/{item_id}/approve", response_model=DecisionOut)
async def approve(
    kind: Kind, item_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(None))
) -> DecisionOut:
    return await service.decide(ctx, kind, item_id, approve=True, note=body.note)


@router.post("/{kind}/{item_id}/reject", response_model=DecisionOut)
async def reject(
    kind: Kind, item_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(None))
) -> DecisionOut:
    return await service.decide(ctx, kind, item_id, approve=False, note=body.note)
