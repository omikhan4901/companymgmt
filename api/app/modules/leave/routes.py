"""Leave API: types, holidays, the work week, balances, requests and adjustments.

Each route only checks who may call it and hands over to `service`.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import check_if_match, set_etag
from app.modules.leave import access, service
from app.modules.leave.schemas import (
    AdjustmentIn,
    AdjustmentOut,
    CalendarEntry,
    DecisionIn,
    HolidayIn,
    HolidayOut,
    LeaveTypeIn,
    LeaveTypeOut,
    LeaveTypePatch,
    PersonBalances,
    PolicyIn,
    PolicyOut,
    QuoteOut,
    RequestIn,
    RequestOut,
)
from app.modules.platform.deps import Ctx, allow

service.register_hooks()

router = APIRouter(prefix="/v1/leave", tags=["leave"])
MODULE = "leave"

Year = Query(default=None, ge=2000, le=2100)


# ---- Settings ---------------------------------------------------------------------------


@router.get("/policy", response_model=PolicyOut)
async def get_policy(ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> PolicyOut:
    return await service.get_policy(ctx)


@router.put("/policy", response_model=PolicyOut)
async def put_policy(body: PolicyIn, ctx: Ctx = Depends(allow(access.SETTINGS, module=MODULE))) -> PolicyOut:
    return await service.set_policy(ctx, body)


@router.get("/types", response_model=list[LeaveTypeOut])
async def list_types(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)), include_inactive: bool = False
) -> list[LeaveTypeOut]:
    return await service.list_types(ctx, include_inactive=include_inactive and ctx.can(access.SETTINGS))


@router.post("/types", response_model=LeaveTypeOut, status_code=201)
async def create_type(
    body: LeaveTypeIn, ctx: Ctx = Depends(allow(access.SETTINGS, module=MODULE))
) -> LeaveTypeOut:
    return await service.create_type(ctx, body)


@router.patch("/types/{leave_type_id}", response_model=LeaveTypeOut)
async def update_type(
    leave_type_id: uuid.UUID,
    body: LeaveTypePatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(access.SETTINGS, module=MODULE)),
) -> LeaveTypeOut:
    current = await service.leave_type(ctx.db, leave_type_id)
    check_if_match(request, current.version)
    out = await service.update_type(ctx, leave_type_id, body, version=current.version)
    set_etag(response, out.version)
    return out


@router.get("/holidays", response_model=list[HolidayOut])
async def list_holidays(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)), year: int | None = Year
) -> list[HolidayOut]:
    return await service.list_holidays(ctx, year or service.local_today(ctx).year)


@router.post("/holidays", response_model=HolidayOut, status_code=201)
async def add_holiday(
    body: HolidayIn, ctx: Ctx = Depends(allow(access.SETTINGS, module=MODULE))
) -> HolidayOut:
    return await service.add_holiday(ctx, body)


@router.delete("/holidays/{holiday_id}", status_code=204)
async def remove_holiday(
    holiday_id: uuid.UUID, ctx: Ctx = Depends(allow(access.SETTINGS, module=MODULE))
) -> Response:
    await service.remove_holiday(ctx, holiday_id)
    return Response(status_code=204)


# ---- Balances ---------------------------------------------------------------------------


@router.get("/balances", response_model=PersonBalances)
async def balances(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    employee_id: uuid.UUID | None = None,
    year: int | None = Year,
) -> PersonBalances:
    return await service.person_balances(ctx, employee_id, year)


@router.get("/balances/team", response_model=list[PersonBalances])
async def team_balances(
    ctx: Ctx = Depends(allow(access.VIEW, module=MODULE)), year: int | None = Year
) -> list[PersonBalances]:
    return await service.team_balances(ctx, year)


# ---- Requests ---------------------------------------------------------------------------


@router.get("/quote", response_model=QuoteOut)
async def quote(
    leave_type_id: uuid.UUID,
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    half_day: Literal["none", "morning", "afternoon"] = "none",
    employee_id: uuid.UUID | None = None,
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
) -> QuoteOut:
    return await service.quote(ctx, leave_type_id, start, end, half_day, employee_id)


@router.post("/requests", response_model=RequestOut, status_code=201)
async def create_request(
    body: RequestIn, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))
) -> RequestOut:
    return await service.create_request(ctx, body)


@router.get("/requests", response_model=list[RequestOut])
async def list_requests(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    status: Literal["pending", "approved", "rejected", "cancelled", "all"] = "all",
    mine: bool = False,
    employee_id: uuid.UUID | None = None,
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
) -> list[RequestOut]:
    return await service.list_requests(
        ctx, status=status, mine=mine, employee_id=employee_id, start=start, end=end
    )


@router.post("/requests/{request_id}/approve", response_model=RequestOut)
async def approve(
    request_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))
) -> RequestOut:
    return await service.approve(ctx, request_id, body.note)


@router.post("/requests/{request_id}/reject", response_model=RequestOut)
async def reject(
    request_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))
) -> RequestOut:
    return await service.reject(ctx, request_id, body.note)


@router.post("/requests/{request_id}/cancel", response_model=RequestOut)
async def cancel(
    request_id: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))
) -> RequestOut:
    return await service.cancel(ctx, request_id, body.note)


@router.get("/calendar", response_model=list[CalendarEntry])
async def calendar(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
) -> list[CalendarEntry]:
    return await service.calendar(ctx, start, end)


# ---- Adjustments ------------------------------------------------------------------------


@router.post("/adjustments", response_model=AdjustmentOut, status_code=201)
async def add_adjustment(
    body: AdjustmentIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> AdjustmentOut:
    return await service.add_adjustment(ctx, body)


@router.get("/adjustments", response_model=list[AdjustmentOut])
async def list_adjustments(
    ctx: Ctx = Depends(allow(access.SELF, module=MODULE)),
    employee_id: uuid.UUID | None = None,
    year: int | None = Year,
) -> list[AdjustmentOut]:
    return await service.list_adjustments(ctx, employee_id, year)
