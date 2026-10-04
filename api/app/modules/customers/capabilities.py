"""Customer capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.customers import access, service
from app.modules.customers.schemas import CustomerOut
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx


class CustomersIn(BaseModel):
    q: str | None = Field(default=None, max_length=100)
    owing: bool = False


@capability(
    "customers.list",
    "Customers and what each owes (dues); `owing` lists only those who owe, largest first.",
    input=CustomersIn,
    output=list[CustomerOut],
    permission=access.VIEW,
    module=access.MODULE,
    route="GET /v1/customers",
)
async def customers(ctx: Ctx, data: CustomersIn) -> list[CustomerOut]:
    return await service.list_customers(ctx, q=data.q, owing=data.owing)
