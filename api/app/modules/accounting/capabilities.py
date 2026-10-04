"""Accounting capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.modules.accounting import access, service
from app.modules.accounting.schemas import ProfitLossOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class PeriodIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start: date = Field(alias="from")
    end: date = Field(alias="to")


@capability(
    "accounting.profit_and_loss",
    "Income, expenses and profit for a period, by account.",
    input=PeriodIn,
    output=ProfitLossOut,
    permission=access.VIEW,
    module=access.MODULE,
    route="GET /v1/accounting/profit-and-loss",
)
async def profit_and_loss(ctx: Ctx, data: PeriodIn) -> ProfitLossOut:
    return await service.profit_and_loss(ctx, data.start, data.end)
