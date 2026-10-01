"""Attendance capabilities (see platform/capabilities.py)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.modules.attendance import access, service
from app.modules.attendance.schemas import PresentOut, StatusOut, TimesheetOut
from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx

MODULE = "attendance"


@capability(
    "attendance.my_status",
    "Whether you're clocked in now and how long you've worked today.",
    output=StatusOut,
    permission=access.SELF,
    module=MODULE,
    route="GET /v1/attendance/status",
)
async def my_status(ctx: Ctx, _: NoInput) -> StatusOut:
    return await service.status(ctx)


@capability(
    "attendance.present",
    "Who is clocked in right now.",
    output=list[PresentOut],
    permission=access.VIEW,
    module=MODULE,
    scoped=True,
    route="GET /v1/attendance/present",
)
async def present(ctx: Ctx, _: NoInput) -> list[PresentOut]:
    return await service.present(ctx)


class TimesheetIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")
    employee_id: uuid.UUID | None = None


@capability(
    "attendance.timesheet",
    "Hours worked per person per day in a month (yours, or everyone in your scope).",
    input=TimesheetIn,
    output=TimesheetOut,
    permission=access.SELF,
    module=MODULE,
    scoped=True,
    route="GET /v1/attendance/timesheet",
)
async def timesheet(ctx: Ctx, data: TimesheetIn) -> TimesheetOut:
    return await service.timesheet(ctx, data.month, data.employee_id)
