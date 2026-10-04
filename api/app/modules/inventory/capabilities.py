"""Inventory capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.inventory import access, service
from app.modules.inventory.schemas import StockOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class StockIn(BaseModel):
    low: bool = False
    q: str | None = Field(default=None, max_length=100)


@capability(
    "inventory.stock",
    "Stock on hand by item (and branch), its cost value, and what's at or below its reorder level (`low`).",
    input=StockIn,
    output=list[StockOut],
    permission=access.VIEW,
    module=access.MODULE,
    route="GET /v1/inventory/stock",
)
async def stock(ctx: Ctx, data: StockIn) -> list[StockOut]:
    return await service.stock(ctx, low_only=data.low, q=data.q)
