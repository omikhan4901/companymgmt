"""Sample data and the first-day checklist.

Sample data goes into the modules that are switched on, marked "(sample)", and is
listed in `sample_records` so removing it takes exactly what was added and nothing a
person made. The checklist looks at the workspace as it is; nothing is stored except
that the owner hid it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core import audit
from app.core.errors import Conflict
from app.core.time import today, utcnow
from app.modules.customers.models import Customer
from app.modules.people.models import Department, Employee
from app.modules.people.service import check_people_limit
from app.modules.platform.catalog import WORKSPACE_MANAGE
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch, Membership, Tenant, User
from app.modules.sales.models import Product, ProductCategory
from app.modules.tasks.models import Project, Task
from app.modules.welcome.models import SampleRecord

MODELS: dict[str, Any] = {
    "departments": Department,
    "employees": Employee,
    "projects": Project,
    "tasks": Task,
    "product_categories": ProductCategory,
    "products": Product,
    "customers": Customer,
}
PEOPLE = (
    ("Karim Mia (sample)", "Tea maker"),
    ("Salma Begum (sample)", "Cook"),
    ("Nusrat Jahan (sample)", "Cashier"),
)
PRODUCTS = (("Tea", 1500), ("Coffee", 4000), ("Samosa", 1000), ("Cake slice", 6000))


class SampleOut(BaseModel):
    present: bool
    records: int


class ChecklistItem(BaseModel):
    key: str
    done: bool
    link: str


class ChecklistOut(BaseModel):
    items: list[ChecklistItem]
    dismissed: bool
    sample_data: bool


async def _has_sample(ctx: Ctx) -> int:
    return int(await ctx.db.scalar(select(func.count()).select_from(SampleRecord)) or 0)


async def sample_status(ctx: Ctx) -> SampleOut:
    ctx.require(WORKSPACE_MANAGE)
    count = await _has_sample(ctx)
    return SampleOut(present=bool(count), records=count)


async def add_sample(ctx: Ctx) -> SampleOut:
    ctx.require(WORKSPACE_MANAGE)
    assert ctx.tenant is not None
    if await _has_sample(ctx):
        raise Conflict("Sample data is already here.", code="sample_present")
    modules = ctx.entitlements.modules if ctx.entitlements else frozenset()
    made: list[tuple[str, Any]] = []

    def keep(table: str, row: Any) -> Any:
        ctx.db.add(row)
        made.append((table, row))
        return row

    await check_people_limit(ctx.db, ctx.tenant_id, adding=len(PEOPLE))
    team = keep("departments", Department(name="Shop floor (sample)"))
    await ctx.db.flush()
    people = [
        keep(
            "employees",
            Employee(
                full_name=name, job_title=job, department_id=team.id, joined_on=today(ctx.tenant.timezone)
            ),
        )
        for name, job in PEOPLE
    ]
    await ctx.db.flush()
    if "tasks" in modules:
        project = keep(
            "projects",
            Project(name="Opening week (sample)", member_ids=[p.id for p in people], created_by=ctx.user.id),
        )
        await ctx.db.flush()
        for i, title in enumerate(("Clean the counter", "Order milk and sugar", "Put up the price list")):
            keep(
                "tasks",
                Task(
                    project_id=project.id,
                    title=title,
                    assignee_id=people[i].id,
                    due_date=today(ctx.tenant.timezone) + timedelta(days=i + 1),
                    position=float(i),
                    created_by=ctx.user.id,
                    source="sample",
                ),
            )
    if "sales" in modules:
        drinks = keep("product_categories", ProductCategory(name="Snacks and drinks (sample)"))
        await ctx.db.flush()
        for i, (name, price) in enumerate(PRODUCTS):
            keep(
                "products",
                Product(
                    name=f"{name} (sample)",
                    price=price,
                    category_id=drinks.id,
                    tax_rate_ids=[],
                    favorite=True,
                    position=i,
                ),
            )
    if "customers" in modules:
        keep("customers", Customer(name="Regular customer (sample)", phone=None))
    await ctx.db.flush()
    ctx.db.add_all(
        SampleRecord(table_name=t, record_id=row.id, position=i) for i, (t, row) in enumerate(made)
    )
    await audit.record(ctx.db, "workspace.sample_added", target_type="workspace", data={"records": len(made)})
    await ctx.db.commit()
    return SampleOut(present=True, records=len(made))


async def remove_sample(ctx: Ctx) -> SampleOut:
    """Remove everything sample data added (what people did with it, like sales of a
    sample item, stays; those rows keep their names)."""
    ctx.require(WORKSPACE_MANAGE)
    rows = [
        (r.table_name, r.record_id)
        for r in await ctx.db.scalars(select(SampleRecord).order_by(SampleRecord.position.desc()))
    ]
    for table_name, record_id in rows:
        model = MODELS.get(table_name)
        if model is None:
            continue
        if model is Product:
            # Products can be on past sales: switch them off instead of deleting.
            product = await ctx.db.get(Product, record_id)
            if product is not None:
                product.active = False
            continue
        try:
            async with ctx.db.begin_nested():
                await ctx.db.execute(delete(model).where(model.id == record_id))
        except IntegrityError:
            # Real records now point at it (a sale to the sample customer, say): keep it.
            continue
    await ctx.db.execute(delete(SampleRecord))
    await audit.record(
        ctx.db, "workspace.sample_removed", target_type="workspace", data={"records": len(rows)}
    )
    await ctx.db.commit()
    return SampleOut(present=False, records=0)


async def _exists(ctx: Ctx, sql: str) -> bool:
    return bool(await ctx.db.scalar(text(f"SELECT EXISTS ({sql})")))


async def checklist(ctx: Ctx) -> ChecklistOut:
    """The few things that make a new workspace ready, worked out from what's there."""
    ctx.require(WORKSPACE_MANAGE)
    assert ctx.tenant is not None
    modules = ctx.entitlements.modules if ctx.entitlements else frozenset()
    tenant = ctx.tenant
    owner_mfa = await ctx.db.scalar(select(User.totp_enabled_at).where(User.id == ctx.user.id))
    people = int(
        await ctx.db.scalar(select(func.count()).select_from(Membership).where(Membership.status == "active"))
        or 0
    )
    items = [
        ChecklistItem(key="details", done=bool(tenant.country), link="/app/settings?tab=workspace"),
        ChecklistItem(key="team", done=people > 1, link="/app/team"),
        ChecklistItem(
            key="branch",
            done=bool(
                await ctx.db.scalar(
                    select(func.count()).select_from(Branch).where(Branch.latitude.is_not(None))
                )
            ),
            link="/app/settings?tab=branches",
        ),
        ChecklistItem(key="two_step", done=owner_mfa is not None, link="/app/account"),
    ]
    if "attendance" in modules:
        items.append(
            ChecklistItem(
                key="clock_in",
                done=await _exists(ctx, "SELECT 1 FROM attendance_records"),
                link="/app/attendance",
            )
        )
    if "sales" in modules:
        items.append(
            ChecklistItem(key="first_sale", done=await _exists(ctx, "SELECT 1 FROM sales"), link="/app/pos")
        )
    if "leave" in modules:
        items.append(
            ChecklistItem(
                key="leave", done=await _exists(ctx, "SELECT 1 FROM leave_requests"), link="/app/leave"
            )
        )
    return ChecklistOut(
        items=items,
        dismissed=tenant.checklist_dismissed_at is not None,
        sample_data=bool(await _has_sample(ctx)),
    )


async def dismiss(ctx: Ctx, hidden: bool) -> ChecklistOut:
    ctx.require(WORKSPACE_MANAGE)
    tenant = await ctx.db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id).with_for_update())
    assert tenant is not None
    tenant.checklist_dismissed_at = utcnow() if hidden else None
    await ctx.db.commit()
    return await checklist(ctx)
