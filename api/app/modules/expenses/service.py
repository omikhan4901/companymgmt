"""Recording and reviewing expenses, receipt photos and petty cash."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core import audit, events
from app.core.errors import Invalid, NotFound
from app.core.time import today
from app.modules.expenses import access
from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.expenses.schemas import (
    CategoryTotal,
    ExpenseCategoryIn,
    ExpenseCategoryOut,
    ExpenseIn,
    ExpenseOut,
    ExpensePatch,
    ExpensesOut,
    TopUpIn,
)
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Tenant, User

MAX_RECEIPT = 5 * 1024 * 1024
# Receipt photos and scans, recognised by their first bytes (never by the name alone).
KINDS = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)
DEFAULT_CATEGORIES = ("Rent", "Utilities", "Supplies", "Transport", "Food and tea", "Repairs", "Other")


def receipt_type(data: bytes) -> str:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, kind in KINDS:
        if data.startswith(magic):
            return kind
    raise Invalid("Use a photo (JPEG, PNG or WebP) or a PDF.", code="receipt_type")


async def _names(ctx: Ctx, rows: list[Expense]) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    categories = dict((await ctx.db.execute(select(ExpenseCategory.id, ExpenseCategory.name))).all())
    users = {r.created_by for r in rows if r.created_by}
    people = (
        dict((await ctx.db.execute(select(User.id, User.name).where(User.id.in_(users)))).all())
        if users
        else {}
    )
    return categories, people


def _out(r: Expense, categories: dict[uuid.UUID, str], people: dict[uuid.UUID, str]) -> ExpenseOut:
    return ExpenseOut(
        id=r.id,
        kind=r.kind,
        occurred_on=r.occurred_on,
        amount=r.amount,
        category_id=r.category_id,
        category_name=categories.get(r.category_id) if r.category_id else None,
        payee=r.payee,
        note=r.note,
        paid_from=r.paid_from,
        branch_id=r.branch_id,
        created_by_name=people.get(r.created_by) if r.created_by else None,
        created_at=r.created_at,
        has_receipt=r.receipt_name is not None,
        receipt_name=r.receipt_name,
        version=r.version,
    )


async def petty_cash(db: AsyncSession) -> int:
    rows = (
        await db.execute(
            select(Expense.kind, func.coalesce(func.sum(Expense.amount), 0))
            .where((Expense.kind == "top_up") | (Expense.paid_from == "petty_cash"))
            .group_by(Expense.kind)
        )
    ).all()
    totals = {k: int(v) for k, v in rows}
    return totals.get("top_up", 0) - totals.get("expense", 0)


async def list_expenses(
    ctx: Ctx, *, start: date | None = None, end: date | None = None, category_id: uuid.UUID | None = None
) -> ExpensesOut:
    ctx.require(access.RECORD)
    query = select(Expense)
    if not ctx.can(access.MANAGE):
        query = query.where(Expense.created_by == ctx.user.id)
    if start:
        query = query.where(Expense.occurred_on >= start)
    if end:
        query = query.where(Expense.occurred_on <= end)
    if category_id:
        query = query.where(Expense.category_id == category_id)
    rows = list(
        await ctx.db.scalars(
            query.order_by(Expense.occurred_on.desc(), Expense.created_at.desc()).limit(1000)
        )
    )
    categories, people = await _names(ctx, rows)
    spent = [r for r in rows if r.kind == "expense"]
    by: dict[uuid.UUID | None, int] = {}
    for r in spent:
        by[r.category_id] = by.get(r.category_id, 0) + r.amount
    return ExpensesOut(
        items=[_out(r, categories, people) for r in rows],
        total=sum(r.amount for r in spent),
        by_category=sorted(
            (
                CategoryTotal(category_id=c, name=categories.get(c, "") if c else "", total=t)
                for c, t in by.items()
            ),
            key=lambda x: -x.total,
        ),
        petty_cash=await petty_cash(ctx.db) if ctx.can(access.MANAGE) else 0,
    )


async def _expense(ctx: Ctx, expense_id: uuid.UUID, *, lock: bool = False) -> Expense:
    query = select(Expense).where(Expense.id == expense_id)
    if lock:
        query = query.with_for_update()
    row = await ctx.db.scalar(query)
    if row is None or (not ctx.can(access.MANAGE) and row.created_by != ctx.user.id):
        raise NotFound()
    return row


async def _check_category(ctx: Ctx, category_id: uuid.UUID | None) -> None:
    if category_id and await ctx.db.get(ExpenseCategory, category_id) is None:
        raise Invalid(errors=[{"field": "category_id", "message": "Choose a category from the list."}])


async def get(ctx: Ctx, expense_id: uuid.UUID) -> ExpenseOut:
    ctx.require(access.RECORD)
    row = await _expense(ctx, expense_id)
    categories, people = await _names(ctx, [row])
    return _out(row, categories, people)


async def create(ctx: Ctx, body: ExpenseIn) -> ExpenseOut:
    ctx.require(access.RECORD)
    assert ctx.tenant is not None
    await _check_category(ctx, body.category_id)
    row = Expense(
        kind="expense",
        occurred_on=body.occurred_on or today(ctx.tenant.timezone),
        amount=body.amount,
        category_id=body.category_id,
        payee=body.payee,
        note=body.note,
        paid_from=body.paid_from,
        branch_id=body.branch_id,
        created_by=ctx.user.id,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "expense.recorded", target_type="expense", target_id=row.id, data={"amount": row.amount}
    )
    await events.emit(
        ctx.db,
        "expense.recorded",
        subject_type="expense",
        subject_id=row.id,
        data={"amount": row.amount, "paid_from": row.paid_from, "category_id": row.category_id},
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def top_up(ctx: Ctx, body: TopUpIn) -> ExpenseOut:
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    row = Expense(
        kind="top_up",
        occurred_on=body.occurred_on or today(ctx.tenant.timezone),
        amount=body.amount,
        note=body.note,
        paid_from="other",
        created_by=ctx.user.id,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "expense.petty_top_up", target_type="expense", target_id=row.id, data={"amount": row.amount}
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def update(ctx: Ctx, expense_id: uuid.UUID, body: ExpensePatch) -> ExpenseOut:
    ctx.require(access.RECORD)
    row = await _expense(ctx, expense_id, lock=True)
    if "category_id" in body.model_fields_set:
        await _check_category(ctx, body.category_id)
    for field in ("amount", "occurred_on", "category_id", "payee", "note", "paid_from"):
        if field in body.model_fields_set and (
            field not in ("amount", "occurred_on", "paid_from") or getattr(body, field) is not None
        ):
            setattr(row, field, getattr(body, field))
    await audit.record(
        ctx.db, "expense.changed", target_type="expense", target_id=row.id, data={"amount": row.amount}
    )
    await ctx.db.commit()
    return await get(ctx, row.id)


async def delete(ctx: Ctx, expense_id: uuid.UUID) -> None:
    ctx.require(access.MANAGE)
    row = await _expense(ctx, expense_id, lock=True)
    await audit.record(
        ctx.db,
        "expense.deleted",
        target_type="expense",
        target_id=row.id,
        data={"amount": row.amount, "payee": row.payee},
    )
    await ctx.db.delete(row)
    await ctx.db.commit()


async def attach(ctx: Ctx, expense_id: uuid.UUID, filename: str, data: bytes) -> ExpenseOut:
    ctx.require(access.RECORD)
    if not data:
        raise Invalid("The file is empty.", code="empty_file")
    kind = receipt_type(data)
    row = await _expense(ctx, expense_id, lock=True)
    row.receipt = data
    row.receipt_type = kind
    row.receipt_name = filename.replace("/", "_").replace("\\", "_")[:200]
    await ctx.db.commit()
    return await get(ctx, row.id)


async def receipt(ctx: Ctx, expense_id: uuid.UUID) -> tuple[bytes, str, str]:
    ctx.require(access.RECORD)
    row = await _expense(ctx, expense_id)
    if row.receipt_name is None:
        raise NotFound()
    loaded = await ctx.db.scalar(
        select(Expense).options(undefer(Expense.receipt)).where(Expense.id == row.id)
    )
    assert loaded is not None
    assert loaded.receipt is not None
    return loaded.receipt, loaded.receipt_name or "receipt", loaded.receipt_type or "application/octet-stream"


async def categories(ctx: Ctx) -> list[ExpenseCategoryOut]:
    ctx.require(access.RECORD)
    rows = await ctx.db.scalars(
        select(ExpenseCategory).order_by(ExpenseCategory.position, ExpenseCategory.name)
    )
    return [
        ExpenseCategoryOut(id=r.id, name=r.name, code=r.code, active=r.active, position=r.position)
        for r in rows
    ]


async def save_category(
    ctx: Ctx, body: ExpenseCategoryIn, category_id: uuid.UUID | None = None
) -> ExpenseCategoryOut:
    ctx.require(access.MANAGE)
    if category_id:
        row = await ctx.db.get(ExpenseCategory, category_id)
        if row is None:
            raise NotFound()
        for k, v in body.model_dump().items():
            setattr(row, k, v)
    else:
        row = ExpenseCategory(**body.model_dump())
        ctx.db.add(row)
    await ctx.db.flush()
    await ctx.db.commit()
    return ExpenseCategoryOut(
        id=row.id, name=row.name, code=row.code, active=row.active, position=row.position
    )


async def drawer_expenses(db: AsyncSession, user_id: uuid.UUID, since: object, until: object | None) -> int:
    """Cash taken from the till by this person in a drawer session (for closing the drawer)."""
    query = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.paid_from == "drawer",
        Expense.kind == "expense",
        Expense.created_by == user_id,
        Expense.created_at >= since,
    )
    if until is not None:
        query = query.where(Expense.created_at <= until)
    return int(await db.scalar(query) or 0)


async def seed(db: AsyncSession, tenant: Tenant, module: str) -> None:
    """Common categories the first time Expenses is switched on (rename or hide any)."""
    if module != "expenses":
        return
    if not await db.scalar(select(func.count()).select_from(ExpenseCategory)):
        for position, name in enumerate(DEFAULT_CATEGORIES):
            db.add(ExpenseCategory(name=name, position=position))
    await db.flush()


def register_hooks() -> None:
    if seed not in hooks.module_enabled:
        hooks.module_enabled.append(seed)
