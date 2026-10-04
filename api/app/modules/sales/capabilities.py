"""Sales capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx
from app.modules.sales import access, service
from app.modules.sales.schemas import SummaryOut


class SummaryIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start: date = Field(alias="from")
    end: date = Field(alias="to")


@capability(
    "sales.summary",
    "Sales for a period: totals, cash, credit, returns, tax by rate, best sellers, by day and by seller.",
    input=SummaryIn,
    output=SummaryOut,
    permission=access.VIEW,
    module=access.MODULE,
    route="GET /v1/sales/summary",
)
async def summary(ctx: Ctx, data: SummaryIn) -> SummaryOut:
    return await service.summary(ctx, data.start, data.end)
