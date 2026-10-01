"""Report capabilities (see platform/capabilities.py)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx
from app.modules.reports import access, service
from app.modules.reports.schemas import OverviewOut


class OverviewIn(BaseModel):
    start: date = Field(alias="from")
    end: date = Field(alias="to")
    department_id: uuid.UUID | None = None


@capability(
    "reports.overview",
    "Headcount, attendance rate and lateness, leave taken and overdue tasks for a period, "
    "for the whole workspace or one department.",
    input=OverviewIn,
    output=OverviewOut,
    permission=access.VIEW,
    module="people",
    route="GET /v1/reports/overview",
)
async def overview(ctx: Ctx, data: OverviewIn) -> OverviewOut:
    return await service.overview(ctx, data.start, data.end, data.department_id)
