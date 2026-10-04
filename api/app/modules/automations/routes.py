"""Automations over HTTP (owners and admins), and the scheduler's tick."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response

from app.core.http import check_if_match
from app.modules.automations import access, engine, service
from app.modules.automations.schemas import (
    AutomationIn,
    AutomationOut,
    AutomationPatch,
    AutomationRunOut,
    EventInfo,
)
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.internal import internal_only

router = APIRouter(prefix="/v1/automations", tags=["automations"])
Manage = Depends(allow(access.MANAGE))


@router.get("", response_model=list[AutomationOut])
async def list_automations(ctx: Ctx = Manage) -> list[AutomationOut]:
    return await service.list_automations(ctx)


@router.get("/events", response_model=list[EventInfo])
async def event_catalog(ctx: Ctx = Manage) -> list[EventInfo]:
    return service.event_catalog()


@router.post("", response_model=AutomationOut, status_code=201)
async def create(body: AutomationIn, ctx: Ctx = Manage) -> AutomationOut:
    return await service.create(ctx, body)


@router.get("/{automation_id}", response_model=AutomationOut)
async def get(automation_id: uuid.UUID, ctx: Ctx = Manage) -> AutomationOut:
    return await service.get(ctx, automation_id)


@router.put("/{automation_id}", response_model=AutomationOut)
async def replace(
    automation_id: uuid.UUID, body: AutomationIn, request: Request, ctx: Ctx = Manage
) -> AutomationOut:
    check_if_match(request, (await service.get(ctx, automation_id)).version)
    return await service.replace(ctx, automation_id, body)


@router.patch("/{automation_id}", response_model=AutomationOut)
async def update(automation_id: uuid.UUID, body: AutomationPatch, ctx: Ctx = Manage) -> AutomationOut:
    return await service.update(ctx, automation_id, body)


@router.delete("/{automation_id}", status_code=204)
async def delete(automation_id: uuid.UUID, ctx: Ctx = Manage) -> Response:
    await service.delete(ctx, automation_id)
    return Response(status_code=204)


@router.post("/{automation_id}/run", response_model=AutomationRunOut)
async def run_now(automation_id: uuid.UUID, ctx: Ctx = Manage) -> AutomationRunOut:
    return await service.run_now(ctx, automation_id)


@router.get("/{automation_id}/runs", response_model=list[AutomationRunOut])
async def runs(automation_id: uuid.UUID, ctx: Ctx = Manage) -> list[AutomationRunOut]:
    return await service.runs(ctx, automation_id)


internal_router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@internal_router.post("/automations/tick")
async def tick(_: None = Depends(internal_only)) -> dict[str, int]:
    """Every 15 minutes: run scheduled automations that are due."""
    return {"runs": await engine.tick()}
