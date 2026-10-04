"""The first-day checklist and sample data over HTTP."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.platform.catalog import WORKSPACE_MANAGE
from app.modules.platform.deps import Ctx, allow
from app.modules.welcome import service
from app.modules.welcome.service import ChecklistOut, SampleOut

router = APIRouter(prefix="/v1/welcome", tags=["welcome"])
Manage = Depends(allow(WORKSPACE_MANAGE))


@router.get("/checklist", response_model=ChecklistOut)
async def checklist(ctx: Ctx = Manage) -> ChecklistOut:
    return await service.checklist(ctx)


class HideIn(BaseModel):
    hidden: bool


@router.put("/checklist", response_model=ChecklistOut)
async def hide(body: HideIn, ctx: Ctx = Manage) -> ChecklistOut:
    return await service.dismiss(ctx, body.hidden)


@router.get("/sample-data", response_model=SampleOut)
async def sample_status(ctx: Ctx = Manage) -> SampleOut:
    return await service.sample_status(ctx)


@router.post("/sample-data", response_model=SampleOut, status_code=201)
async def add_sample(ctx: Ctx = Manage) -> SampleOut:
    """Fill the workspace with a few sample people, tasks and items to try things."""
    return await service.add_sample(ctx)


@router.delete("/sample-data", response_model=SampleOut)
async def remove_sample(ctx: Ctx = Manage) -> SampleOut:
    return await service.remove_sample(ctx)
