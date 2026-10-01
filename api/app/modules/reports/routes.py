"""Reports over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.platform.deps import Ctx, allow
from app.modules.reports import access, service
from app.modules.reports.schemas import OverviewOut

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/overview", response_model=OverviewOut)
async def overview(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    department_id: uuid.UUID | None = None,
    ctx: Ctx = Depends(allow(access.VIEW, module="people")),
) -> OverviewOut:
    return await service.overview(ctx, start, end, department_id)
