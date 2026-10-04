"""Leave capabilities (see platform/capabilities.py)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.leave import access, service
from app.modules.leave.schemas import (
    CalendarEntry,
    DecisionIn,
    LeaveTypeOut,
    PersonBalances,
    RequestIn,
    RequestOut,
)
from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx

MODULE = "leave"


class BalancesIn(BaseModel):
    employee_id: uuid.UUID | None = Field(default=None, description="Leave out for your own")
    year: int | None = Field(default=None, ge=2000, le=2100)


@capability(
    "leave.balances",
    "Leave left by type for one person (yourself, or someone in your scope).",
    input=BalancesIn,
    output=PersonBalances,
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/leave/balances",
)
async def balances(ctx: Ctx, data: BalancesIn) -> PersonBalances:
    return await service.person_balances(ctx, data.employee_id, data.year)


class YearIn(BaseModel):
    year: int | None = Field(default=None, ge=2000, le=2100)


@capability(
    "leave.team_balances",
    "Everyone's leave balances in your scope.",
    input=YearIn,
    output=list[PersonBalances],
    permission=access.VIEW,
    module=MODULE,
    scoped=True,
    route="GET /v1/leave/balances/team",
)
async def team_balances(ctx: Ctx, data: YearIn) -> list[PersonBalances]:
    return await service.team_balances(ctx, data.year)


class RequestsIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["pending", "approved", "rejected", "cancelled", "all"] = "all"
    mine: bool = False
    employee_id: uuid.UUID | None = None
    start: date | None = Field(default=None, alias="from")
    end: date | None = Field(default=None, alias="to")


@capability(
    "leave.requests",
    "Leave requests: your own, or those you may see or approve.",
    input=RequestsIn,
    output=list[RequestOut],
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/leave/requests",
)
async def requests(ctx: Ctx, data: RequestsIn) -> list[RequestOut]:
    return await service.list_requests(
        ctx, status=data.status, mine=data.mine, employee_id=data.employee_id, start=data.start, end=data.end
    )


class CalendarIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start: date = Field(alias="from")
    end: date = Field(alias="to")


@capability(
    "leave.calendar",
    "Who is away between two dates.",
    input=CalendarIn,
    output=list[CalendarEntry],
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/leave/calendar",
)
async def calendar(ctx: Ctx, data: CalendarIn) -> list[CalendarEntry]:
    return await service.calendar(ctx, data.start, data.end)


@capability(
    "leave.types",
    "The kinds of leave this workspace has.",
    output=list[LeaveTypeOut],
    permission=access.SELF,
    module=MODULE,
    route="GET /v1/leave/types",
)
async def types(ctx: Ctx, _: NoInput) -> list[LeaveTypeOut]:
    return await service.list_types(ctx)


@capability(
    "leave.request",
    "Ask for leave (for yourself, or someone else with leave.manage).",
    input=RequestIn,
    output=RequestOut,
    permission=access.SELF,
    module=MODULE,
    kind="write",
    route="POST /v1/leave/requests",
)
async def request(ctx: Ctx, data: RequestIn) -> RequestOut:
    return await service.create_request(ctx, data)


class DecideIn(DecisionIn):
    request_id: uuid.UUID
    decision: Literal["approve", "reject"]


@capability(
    "leave.decide",
    "Approve or turn down a leave request you're allowed to decide, with an optional note.",
    input=DecideIn,
    output=RequestOut,
    permission=access.APPROVE,
    module=MODULE,
    kind="write",
    scoped=True,
    route="POST /v1/leave/requests/{request_id}/approve",
)
async def decide(ctx: Ctx, data: DecideIn) -> RequestOut:
    if data.decision == "approve":
        return await service.approve(ctx, data.request_id, data.note)
    return await service.reject(ctx, data.request_id, data.note)
