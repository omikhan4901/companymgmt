"""Customers and their dues. Sales on credit and returns are posted here by the sales
module; payments and adjustments by people who manage customers."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, or_, select

from app.core import audit, events
from app.core.errors import Invalid, NotFound
from app.core.time import today
from app.modules.customers import access
from app.modules.customers.models import Customer, CustomerEntry
from app.modules.customers.schemas import (
    CustomerIn,
    CustomerOut,
    CustomerPatch,
    DuesAdjustmentIn,
    EntryOut,
    PaymentIn,
    StatementOut,
)
from app.modules.platform.deps import Ctx


async def _balances(ctx: Ctx, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, date | None]]:
    if not ids:
        return {}
    rows = (
        await ctx.db.execute(
            select(
                CustomerEntry.customer_id, func.sum(CustomerEntry.amount), func.max(CustomerEntry.occurred_on)
            )
            .where(CustomerEntry.customer_id.in_(ids))
            .group_by(CustomerEntry.customer_id)
        )
    ).all()
    return {c: (int(total or 0), last) for c, total, last in rows}


async def _out(ctx: Ctx, rows: Sequence[Customer]) -> list[CustomerOut]:
    balances = await _balances(ctx, [r.id for r in rows])
    return [
        CustomerOut(
            id=r.id,
            name=r.name,
            phone=r.phone,
            address=r.address,
            note=r.note,
            credit_limit=r.credit_limit,
            active=r.active,
            balance=balances.get(r.id, (0, None))[0],
            last_activity=balances.get(r.id, (0, None))[1],
            version=r.version,
        )
        for r in rows
    ]


async def customer(ctx: Ctx, customer_id: uuid.UUID, *, lock: bool = False) -> Customer:
    query = select(Customer).where(Customer.id == customer_id)
    if lock:
        query = query.with_for_update()
    found = await ctx.db.scalar(query)
    if found is None:
        raise NotFound()
    return found


async def balance(ctx: Ctx, customer_id: uuid.UUID) -> int:
    return (await _balances(ctx, [customer_id])).get(customer_id, (0, None))[0]


async def list_customers(ctx: Ctx, *, q: str | None = None, owing: bool = False) -> list[CustomerOut]:
    ctx.require(access.VIEW)
    query = select(Customer).where(Customer.active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Customer.name.ilike(like), Customer.phone.ilike(like)))
    rows = list(await ctx.db.scalars(query.order_by(Customer.name).limit(500)))
    out = await _out(ctx, rows)
    if owing:
        out = sorted((c for c in out if c.balance > 0), key=lambda c: -c.balance)
    return out


async def get(ctx: Ctx, customer_id: uuid.UUID) -> CustomerOut:
    ctx.require(access.VIEW)
    return (await _out(ctx, [await customer(ctx, customer_id)]))[0]


async def create(ctx: Ctx, body: CustomerIn) -> CustomerOut:
    ctx.require(access.MANAGE)
    row = Customer(**body.model_dump())
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "customer.created", target_type="customer", target_id=row.id, data={"name": row.name}
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def update(ctx: Ctx, customer_id: uuid.UUID, body: CustomerPatch) -> CustomerOut:
    ctx.require(access.MANAGE)
    row = await customer(ctx, customer_id, lock=True)
    for field in ("name", "phone", "address", "note", "credit_limit", "active"):
        if field in body.model_fields_set and (field != "name" or body.name is not None):
            setattr(row, field, getattr(body, field))
    if body.no_limit:
        row.credit_limit = None
    await audit.record(
        ctx.db, "customer.changed", target_type="customer", target_id=row.id, data={"name": row.name}
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def post(
    ctx: Ctx,
    customer_id: uuid.UUID,
    kind: str,
    amount: int,
    *,
    sale_id: uuid.UUID | None = None,
    note: str | None = None,
    occurred_on: date | None = None,
    check_limit: bool = False,
) -> CustomerEntry:
    """Add a line to a customer's account (in the caller's transaction)."""
    assert ctx.tenant is not None
    row = await customer(ctx, customer_id, lock=True)
    if check_limit and row.credit_limit is not None and amount > 0:
        owed = await balance(ctx, customer_id)
        if owed + amount > row.credit_limit:
            raise Invalid(
                f"{row.name} can owe up to {row.credit_limit}; this would make it {owed + amount}.",
                code="credit_limit",
            )
    entry = CustomerEntry(
        customer_id=customer_id,
        kind=kind,
        amount=amount,
        occurred_on=occurred_on or today(ctx.tenant.timezone),
        sale_id=sale_id,
        note=note,
        created_by=ctx.user.id,
    )
    ctx.db.add(entry)
    await ctx.db.flush()
    return entry


async def pay(ctx: Ctx, customer_id: uuid.UUID, body: PaymentIn) -> CustomerOut:
    ctx.require(access.MANAGE)
    entry = await post(
        ctx, customer_id, "payment", -body.amount, note=body.note, occurred_on=body.occurred_on
    )
    await audit.record(
        ctx.db,
        "customer.payment",
        target_type="customer",
        target_id=customer_id,
        data={"amount": body.amount},
    )
    await events.emit(
        ctx.db,
        "customer.paid",
        subject_type="customer",
        subject_id=customer_id,
        data={"amount": body.amount, "entry_id": entry.id},
    )
    await ctx.db.commit()
    return await get(ctx, customer_id)


async def adjust(ctx: Ctx, customer_id: uuid.UUID, body: DuesAdjustmentIn) -> CustomerOut:
    ctx.require(access.MANAGE)
    if body.amount == 0:
        raise Invalid(errors=[{"field": "amount", "message": "Enter an amount."}])
    await post(ctx, customer_id, "adjustment", body.amount, note=body.note, occurred_on=body.occurred_on)
    await audit.record(
        ctx.db,
        "customer.adjusted",
        target_type="customer",
        target_id=customer_id,
        data={"amount": body.amount, "note": body.note},
    )
    await ctx.db.commit()
    return await get(ctx, customer_id)


async def statement(
    ctx: Ctx, customer_id: uuid.UUID, start: date | None = None, end: date | None = None
) -> StatementOut:
    ctx.require(access.VIEW)
    who = await get(ctx, customer_id)
    opening = 0
    if start is not None:
        opening = int(
            await ctx.db.scalar(
                select(func.coalesce(func.sum(CustomerEntry.amount), 0)).where(
                    CustomerEntry.customer_id == customer_id, CustomerEntry.occurred_on < start
                )
            )
            or 0
        )
    query = select(CustomerEntry).where(CustomerEntry.customer_id == customer_id)
    if start is not None:
        query = query.where(CustomerEntry.occurred_on >= start)
    if end is not None:
        query = query.where(CustomerEntry.occurred_on <= end)
    running = opening
    entries = []
    for e in await ctx.db.scalars(query.order_by(CustomerEntry.occurred_on, CustomerEntry.created_at)):
        running += e.amount
        entries.append(
            EntryOut(
                id=e.id,
                kind=e.kind,
                amount=e.amount,
                occurred_on=e.occurred_on,
                sale_id=e.sale_id,
                note=e.note,
                created_at=e.created_at,
                balance=running,
            )
        )
    return StatementOut(customer=who, opening=opening, entries=entries, closing=running, start=start, end=end)
