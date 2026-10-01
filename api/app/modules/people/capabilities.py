"""People capabilities (see platform/capabilities.py)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schema import Page
from app.modules.people import service
from app.modules.people.access import PEOPLE_VIEW
from app.modules.people.schemas import EmployeeOut, employee_out
from app.modules.platform.capabilities import capability
from app.modules.platform.deps import Ctx

MODULE = "people"


class SearchIn(BaseModel):
    q: str | None = Field(default=None, max_length=100, description="Name, code, email or phone")
    department_id: uuid.UUID | None = None
    status: Literal["active", "inactive", "left", "all"] = "active"
    limit: int = Field(default=50, ge=1, le=200)


@capability(
    "people.search",
    "Find people by name, code, email or phone, optionally in one department.",
    input=SearchIn,
    output=Page[EmployeeOut],
    permission=PEOPLE_VIEW,
    module=MODULE,
    scoped=True,
    route="GET /v1/people",
)
async def search(ctx: Ctx, data: SearchIn) -> Page[EmployeeOut]:
    return await service.search_people(
        ctx, q=data.q, department_id=data.department_id, status=data.status, limit=data.limit
    )


class PersonIn(BaseModel):
    employee_id: uuid.UUID


@capability(
    "people.get",
    "One person's profile: your own, or someone in your scope if you may see people.",
    input=PersonIn,
    output=EmployeeOut,
    permission=None,
    module=MODULE,
    scoped=True,
    route="GET /v1/people/{employee_id}",
)
async def get(ctx: Ctx, data: PersonIn) -> EmployeeOut:
    return employee_out(await service.get_person(ctx, data.employee_id))
