"""The books: automatic postings, backfill, entries typed by hand, reports, period lock
and tax returns from templates.

Automatic postings run after the change is saved (through the outbox), so a problem in
the books can never stop a sale. Each is recorded once per source and reason, so a
retry or a backfill never posts twice.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Conflict, Invalid, NotFound
from app.core.time import local_date, today
from app.modules.accounting import access, postings
from app.modules.accounting.chart import STARTING_CHART
from app.modules.accounting.models import (
    Account,
    AccountingSettings,
    JournalEntry,
    JournalLine,
    TaxReturnTemplate,
)
from app.modules.accounting.schemas import (
    AccountIn,
    AccountOut,
    BalanceSheetOut,
    BoxOut,
    EntryIn,
    EntryOut,
    LedgerOut,
    LedgerRow,
    LineOut,
    ProfitLossOut,
    ReportRow,
    SettingsIn,
    SettingsOut,
    TaxReturnOut,
    TemplateIn,
    TemplateOut,
    TrialBalanceOut,
)
from app.modules.customers.models import Customer, CustomerEntry
from app.modules.expenses.models import Expense
from app.modules.inventory.costing import money
from app.modules.inventory.models import Purchase, StockMovement, Supplier, SupplierEntry
from app.modules.payroll.models import PayrollRun
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx, load_entitlements
from app.modules.platform.models import Tenant
from app.modules.sales.models import Product, Sale, SaleLine

log = logging.getLogger(__name__)
CASH_ROLES = ("cash", "drawer", "petty_cash", "bank")
DEBIT_NORMAL = ("asset", "expense")


# ---- Accounts and settings ------------------------------------------------------------


async def _settings(db: AsyncSession, *, lock: bool = False) -> AccountingSettings:
    query = select(AccountingSettings)
    if lock:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        row = AccountingSettings(tax_accounts={}, expense_accounts={}, next_number=1)
        db.add(row)
        await db.flush()
    return row


async def _seed_chart(db: AsyncSession) -> None:
    have = set(await db.scalars(select(Account.code)))
    roles = set(await db.scalars(select(Account.role).where(Account.role.is_not(None))))
    for code, name, kind, role in STARTING_CHART:
        if code not in have and role not in roles:
            db.add(Account(code=code, name=name, type=kind, role=role))
    await db.flush()


async def _role(db: AsyncSession, role: str) -> uuid.UUID:
    found = await db.scalar(select(Account.id).where(Account.role == role))
    if found:
        return found
    # A role's account was removed: put it back from the starting chart.
    for code, name, kind, r in STARTING_CHART:
        if r == role:
            used = set(await db.scalars(select(Account.code)))
            account = Account(
                code=code if code not in used else f"{code}-{uuid.uuid4().hex[:4]}",
                name=name,
                type=kind,
                role=role,
            )
            db.add(account)
            await db.flush()
            return account.id
    raise ValueError(f"Unknown account role {role}")


# ---- Writing entries ------------------------------------------------------------------


async def _exists(db: AsyncSession, source_type: str, source_id: uuid.UUID, reason: str) -> bool:
    return (
        await db.scalar(
            select(JournalEntry.id).where(
                JournalEntry.source_type == source_type,
                JournalEntry.source_id == source_id,
                JournalEntry.reason == reason,
            )
        )
    ) is not None


async def write(
    db: AsyncSession,
    posting: postings.Posting,
    entry_date: date,
    *,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    reason: str = "post",
    user_id: uuid.UUID | None = None,
) -> JournalEntry | None:
    """Save a posting. Returns None when there was nothing to post or it was posted before."""
    legs = [leg for leg in posting.legs if leg.amount]
    if not legs:
        return None
    if not postings.balanced(legs):
        raise ValueError(f"Unbalanced posting: {posting.memo}")
    if (
        source_id is not None
        and source_type is not None
        and await _exists(db, source_type, source_id, reason)
    ):
        return None
    settings = await _settings(db, lock=True)
    memo = posting.memo
    if settings.locked_until and entry_date <= settings.locked_until:
        memo = f"{memo} (dated {entry_date}, a locked period)"
        entry_date = settings.locked_until + timedelta(days=1)
    entry = JournalEntry(
        number=settings.next_number,
        entry_date=entry_date,
        memo=memo[:300],
        source_type=source_type,
        source_id=source_id,
        reason=reason,
        created_by=user_id,
    )
    settings.next_number += 1
    db.add(entry)
    await db.flush()
    for i, leg in enumerate(legs):
        account = leg.account if isinstance(leg.account, uuid.UUID) else await _role(db, leg.account)
        debit, credit = postings.sides(leg.amount)
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=account,
                debit=debit,
                credit=credit,
                description=leg.description,
                tax_rate_id=leg.tax_rate_id,
                tax_base=leg.tax_base,
                position=i,
            )
        )
    await db.flush()
    return entry


async def reverse_source(
    db: AsyncSession, source_type: str, source_id: uuid.UUID, entry_date: date, why: str
) -> int:
    """Reverse every entry still standing for a source (a void, a deleted or changed expense)."""
    entries = list(
        await db.scalars(
            select(JournalEntry).where(
                JournalEntry.source_type == source_type,
                JournalEntry.source_id == source_id,
                JournalEntry.reversed_by.is_(None),
                ~JournalEntry.reason.startswith("reverse:"),
            )
        )
    )
    done = 0
    for entry in entries:
        lines = list(
            await db.scalars(
                select(JournalLine).where(JournalLine.entry_id == entry.id).order_by(JournalLine.position)
            )
        )
        legs = [
            postings.Leg(
                line.account_id, line.debit - line.credit, line.description, line.tax_rate_id, line.tax_base
            )
            for line in lines
        ]
        reversal = await write(
            db,
            postings.Posting(f"{why}: #{entry.number}", postings.reverse(legs)),
            entry_date,
            source_type=source_type,
            source_id=source_id,
            reason=f"reverse:{entry.id}",
        )
        if reversal:
            entry.reversed_by = reversal.id
            done += 1
    return done


# ---- Automatic postings ---------------------------------------------------------------


async def _on(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    return "accounting" in (await load_entitlements(db, tenant_id)).modules


async def _tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None
    return tenant


def _tax_map(settings: AccountingSettings, side: str) -> dict[uuid.UUID, uuid.UUID]:
    out = {}
    for rate_id, accounts in (settings.tax_accounts or {}).items():
        if isinstance(accounts, dict) and accounts.get(side):
            out[uuid.UUID(rate_id)] = uuid.UUID(str(accounts[side]))
    return out


async def post_sale(db: AsyncSession, tenant: Tenant, sale: Sale) -> None:
    lines = list(await db.scalars(select(SaleLine).where(SaleLine.sale_id == sale.id)))
    facts = [
        postings.SaleLineFacts(
            net=line.net, taxes=[(uuid.UUID(str(t["id"])), int(t["amount"])) for t in line.taxes or []]
        )
        for line in lines
    ]
    settings = await _settings(db)
    posting = postings.sale(
        sale.number,
        sale.kind,
        sale.paid_cash - sale.change,
        sale.on_account,
        sale.rounding,
        facts,
        _tax_map(settings, "output"),
    )
    await write(
        db,
        posting,
        local_date(sale.sold_at, tenant.timezone),
        source_type="sale",
        source_id=sale.id,
        user_id=sale.sold_by,
    )


async def post_stock(db: AsyncSession, tenant: Tenant, movement: StockMovement) -> None:
    name = await db.scalar(select(Product.name).where(Product.id == movement.product_id)) or "item"
    posting = postings.stock(movement.kind, money(movement.value), name)
    if posting:
        await write(
            db,
            posting,
            local_date(movement.occurred_at, tenant.timezone),
            source_type="stock_movement",
            source_id=movement.id,
        )


async def post_purchase(db: AsyncSession, purchase: Purchase) -> None:
    settings = await _settings(db)
    supplier = await db.get(Supplier, purchase.supplier_id) if purchase.supplier_id else None
    taxes = [
        (uuid.UUID(str(line["tax_rate_id"])), int(str(line["tax"])), int(str(line["amount"])))
        for line in purchase.lines or []
        if line.get("tax_rate_id")
    ]
    posting = postings.purchase(
        f"{purchase.reference or ''} {supplier.name if supplier else ''}".strip(),
        purchase.net,
        taxes,
        purchase.paid,
        purchase.paid_from,
        purchase.total - purchase.paid,
        _tax_map(settings, "input"),
    )
    await write(
        db,
        posting,
        purchase.received_on,
        source_type="purchase",
        source_id=purchase.id,
        user_id=purchase.created_by,
    )


async def post_expense(db: AsyncSession, expense: Expense, reason: str = "post") -> None:
    if expense.kind == "top_up":
        posting = postings.petty_top_up(expense.amount)
    else:
        settings = await _settings(db)
        mapped = (
            (settings.expense_accounts or {}).get(str(expense.category_id)) if expense.category_id else None
        )
        posting = postings.expense(
            f"Expense: {expense.payee or 'unnamed'}",
            expense.amount,
            expense.paid_from,
            uuid.UUID(str(mapped)) if mapped else None,
        )
    await write(
        db,
        posting,
        expense.occurred_on,
        source_type="expense",
        source_id=expense.id,
        reason=reason,
        user_id=expense.created_by,
    )


async def post_customer_entry(db: AsyncSession, entry: CustomerEntry) -> None:
    customer = await db.get(Customer, entry.customer_id)
    name = customer.name if customer else "customer"
    if entry.kind == "payment":
        posting = postings.customer_payment(name, -entry.amount)
    elif entry.kind == "adjustment" and entry.sale_id is None:
        posting = postings.customer_adjustment(name, entry.amount, entry.note)
    else:
        return  # Sales, returns and voids post through the sale itself.
    await write(
        db,
        posting,
        entry.occurred_on,
        source_type="customer_entry",
        source_id=entry.id,
        user_id=entry.created_by,
    )


async def post_supplier_payment(db: AsyncSession, entry: SupplierEntry) -> None:
    if entry.kind != "payment":
        return
    supplier = await db.get(Supplier, entry.supplier_id)
    posting = postings.supplier_payment(
        supplier.name if supplier else "supplier", -entry.amount, entry.paid_from or "bank"
    )
    await write(
        db,
        posting,
        entry.occurred_on,
        source_type="supplier_entry",
        source_id=entry.id,
        user_id=entry.created_by,
    )


async def post_payroll(db: AsyncSession, tenant: Tenant, run: PayrollRun) -> None:
    when = local_date(run.finalized_at, tenant.timezone) if run.finalized_at else today(tenant.timezone)
    posting = postings.payroll(run.period, run.gross, run.net, run.deductions)
    await write(db, posting, when, source_type="payroll_run", source_id=run.id, user_id=run.finalized_by)


def _subject(event: events.Event) -> uuid.UUID:
    return uuid.UUID(str(event.subject_id))


async def _guarded(db: AsyncSession, event: events.Event, work: Any) -> None:
    if not await _on(db, event.tenant_id):
        return
    try:
        await work()
    except Exception:  # never lose the outbox delivery over one bad posting; log it
        log.exception("posting failed", extra={"event": event.name, "subject": event.subject_id})
        raise


@events.on("sale.completed", later=True)
@events.on("sale.returned", later=True)
async def _sale(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        sale = await db.get(Sale, _subject(event))
        if sale:
            await post_sale(db, await _tenant(db, event.tenant_id), sale)

    await _guarded(db, event, work)


@events.on("sale.voided", later=True)
async def _void(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        tenant = await _tenant(db, event.tenant_id)
        await reverse_source(db, "sale", _subject(event), today(tenant.timezone), "Void")

    await _guarded(db, event, work)


@events.on("stock.moved", later=True)
async def _stock(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        movement = await db.get(StockMovement, _subject(event))
        if movement:
            await post_stock(db, await _tenant(db, event.tenant_id), movement)

    await _guarded(db, event, work)


@events.on("purchase.received", later=True)
async def _purchase(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        purchase = await db.get(Purchase, _subject(event))
        if purchase:
            await post_purchase(db, purchase)

    await _guarded(db, event, work)


@events.on("supplier.paid", later=True)
async def _supplier_paid(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        entry = await db.get(SupplierEntry, _subject(event))
        if entry:
            await post_supplier_payment(db, entry)

    await _guarded(db, event, work)


@events.on("customer.paid", later=True)
@events.on("customer.adjusted", later=True)
async def _customer(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        entry_id = event.data.get("entry_id")
        entry = await db.get(CustomerEntry, uuid.UUID(str(entry_id))) if entry_id else None
        if entry:
            await post_customer_entry(db, entry)

    await _guarded(db, event, work)


@events.on("expense.recorded", later=True)
@events.on("expense.petty_top_up", later=True)
async def _expense(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        expense = await db.get(Expense, _subject(event))
        if expense:
            await post_expense(db, expense)

    await _guarded(db, event, work)


@events.on("expense.changed", later=True)
async def _expense_changed(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        expense = await db.get(Expense, _subject(event))
        if expense:
            tenant = await _tenant(db, event.tenant_id)
            await reverse_source(db, "expense", expense.id, today(tenant.timezone), "Changed")
            await post_expense(db, expense, reason=f"post:{expense.version}:{event.id}")

    await _guarded(db, event, work)


@events.on("expense.deleted", later=True)
async def _expense_deleted(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        tenant = await _tenant(db, event.tenant_id)
        await reverse_source(db, "expense", _subject(event), today(tenant.timezone), "Deleted")

    await _guarded(db, event, work)


@events.on("payroll.finalized", later=True)
async def _payroll(db: AsyncSession, event: events.Event) -> None:
    async def work() -> None:
        run = await db.get(PayrollRun, _subject(event))
        if run:
            await post_payroll(db, await _tenant(db, event.tenant_id), run)

    await _guarded(db, event, work)


# ---- Backfill -------------------------------------------------------------------------


async def backfill(db: AsyncSession, tenant: Tenant) -> int:
    """Post everything that happened before the books were switched on (safe to repeat)."""
    before = int(await db.scalar(select(func.count()).select_from(JournalEntry)) or 0)
    for sale in await db.scalars(select(Sale).order_by(Sale.sold_at)):
        await post_sale(db, tenant, sale)
        if sale.status == "voided":
            await reverse_source(
                db, "sale", sale.id, local_date(sale.voided_at or sale.sold_at, tenant.timezone), "Void"
            )
    for movement in await db.scalars(select(StockMovement).order_by(StockMovement.occurred_at)):
        await post_stock(db, tenant, movement)
    for purchase in await db.scalars(select(Purchase).order_by(Purchase.received_on)):
        await post_purchase(db, purchase)
    for entry in await db.scalars(select(SupplierEntry).where(SupplierEntry.kind == "payment")):
        await post_supplier_payment(db, entry)
    for centry in await db.scalars(
        select(CustomerEntry).where(CustomerEntry.kind.in_(("payment", "adjustment")))
    ):
        await post_customer_entry(db, centry)
    for expense in await db.scalars(select(Expense).order_by(Expense.occurred_on)):
        await post_expense(db, expense)
    for run in await db.scalars(select(PayrollRun).where(PayrollRun.status.in_(("finalized", "paid")))):
        await post_payroll(db, tenant, run)
    after = int(await db.scalar(select(func.count()).select_from(JournalEntry)) or 0)
    return after - before


async def seed(db: AsyncSession, tenant: Tenant, module: str) -> None:
    """Switching the books on: a starting chart, then everything so far."""
    if module != "accounting":
        return
    await _settings(db)
    await _seed_chart(db)
    await backfill(db, tenant)


def register_hooks() -> None:
    if seed not in hooks.module_enabled:
        hooks.module_enabled.append(seed)


async def run_backfill(ctx: Ctx) -> int:
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    await _seed_chart(ctx.db)
    count = await backfill(ctx.db, ctx.tenant)
    await audit.record(ctx.db, "accounting.backfilled", target_type="workspace", data={"entries": count})
    await ctx.db.commit()
    return count


# ---- Accounts, settings and hand-made entries -----------------------------------------


def _account_out(a: Account) -> AccountOut:
    return AccountOut(
        id=a.id,
        code=a.code,
        name=a.name,
        type=a.type,
        role=a.role,
        active=a.active,
        description=a.description,
        version=a.version,
    )


async def accounts(ctx: Ctx) -> list[AccountOut]:
    ctx.require(access.VIEW)
    return [_account_out(a) for a in await ctx.db.scalars(select(Account).order_by(Account.code))]


async def save_account(ctx: Ctx, body: AccountIn, account_id: uuid.UUID | None = None) -> AccountOut:
    ctx.require(access.MANAGE)
    if await ctx.db.scalar(select(Account.id).where(Account.code == body.code, Account.id != account_id)):
        raise Invalid(errors=[{"field": "code", "message": "Another account has this code."}])
    if account_id:
        row = await ctx.db.get(Account, account_id)
        if row is None:
            raise NotFound()
        used = await ctx.db.scalar(
            select(func.count()).select_from(JournalLine).where(JournalLine.account_id == row.id)
        )
        if used and body.type != row.type:
            raise Conflict("This account has entries; its type can't change.", code="account_used")
        if row.role and not body.active:
            raise Conflict(
                "Automatic postings use this account; give its role to another first.", code="account_in_use"
            )
        row.code, row.name, row.type, row.active, row.description = (
            body.code,
            body.name,
            body.type,
            body.active,
            body.description,
        )
    else:
        row = Account(
            code=body.code, name=body.name, type=body.type, active=body.active, description=body.description
        )
        ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "accounting.account_saved",
        target_type="account",
        target_id=row.id,
        data={"code": row.code, "name": row.name},
    )
    await ctx.db.commit()
    return _account_out(row)


def _settings_out(s: AccountingSettings) -> SettingsOut:
    return SettingsOut(
        locked_until=s.locked_until,
        tax_accounts=s.tax_accounts or {},
        expense_accounts=s.expense_accounts or {},
        version=s.version,
    )


async def get_settings(ctx: Ctx) -> SettingsOut:
    ctx.require(access.VIEW)
    return _settings_out(await _settings(ctx.db))


async def save_settings(ctx: Ctx, body: SettingsIn) -> SettingsOut:
    ctx.require(access.MANAGE)
    row = await _settings(ctx.db, lock=True)
    ids = {uuid.UUID(str(v)) for m in body.tax_accounts.values() for v in m.values() if v} | {
        uuid.UUID(str(v)) for v in body.expense_accounts.values() if v
    }
    if ids and len(set(await ctx.db.scalars(select(Account.id).where(Account.id.in_(ids))))) != len(ids):
        raise Invalid("Choose accounts from your chart.", code="unknown_account")
    before = row.locked_until
    row.locked_until = body.locked_until
    row.tax_accounts = {k: {s: str(v) for s, v in m.items() if v} for k, m in body.tax_accounts.items()}
    row.expense_accounts = {k: str(v) for k, v in body.expense_accounts.items() if v}
    await audit.record(
        ctx.db,
        "accounting.settings_changed",
        target_type="workspace",
        data={"locked_until": [str(before), str(row.locked_until)]},
    )
    await ctx.db.commit()
    return _settings_out(row)


async def _entry_out(ctx: Ctx, e: JournalEntry) -> EntryOut:
    rows = (
        await ctx.db.execute(
            select(JournalLine, Account.code, Account.name)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalLine.entry_id == e.id)
            .order_by(JournalLine.position)
        )
    ).all()
    return EntryOut(
        id=e.id,
        number=e.number,
        entry_date=e.entry_date,
        memo=e.memo,
        source_type=e.source_type,
        source_id=e.source_id,
        reversed_by=e.reversed_by,
        lines=[
            LineOut(
                account_id=line.account_id,
                account_code=code,
                account_name=name,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
            )
            for line, code, name in rows
        ],
    )


async def entries(
    ctx: Ctx, *, start: date | None = None, end: date | None = None, limit: int = 200
) -> list[EntryOut]:
    ctx.require(access.VIEW)
    query = select(JournalEntry)
    if start:
        query = query.where(JournalEntry.entry_date >= start)
    if end:
        query = query.where(JournalEntry.entry_date <= end)
    rows = await ctx.db.scalars(
        query.order_by(JournalEntry.entry_date.desc(), JournalEntry.number.desc()).limit(min(limit, 1000))
    )
    return [await _entry_out(ctx, e) for e in rows]


async def post_manual(ctx: Ctx, body: EntryIn) -> EntryOut:
    ctx.require(access.MANAGE)
    settings = await _settings(ctx.db)
    if settings.locked_until and body.entry_date <= settings.locked_until:
        raise Conflict(f"The books are locked until {settings.locked_until}.", code="period_locked")
    ids = {line.account_id for line in body.lines}
    found = set(await ctx.db.scalars(select(Account.id).where(Account.id.in_(ids), Account.active.is_(True))))
    if found != ids:
        raise Invalid(errors=[{"field": "lines", "message": "Choose active accounts from your chart."}])
    legs = [postings.Leg(line.account_id, line.debit - line.credit, line.description) for line in body.lines]
    if not postings.balanced(legs):
        raise Invalid(errors=[{"field": "lines", "message": "Debits and credits must be equal."}])
    entry = await write(ctx.db, postings.Posting(body.memo, legs), body.entry_date, user_id=ctx.user.id)
    assert entry is not None
    await audit.record(
        ctx.db,
        "accounting.entry_posted",
        target_type="journal_entry",
        target_id=entry.id,
        data={"memo": body.memo},
    )
    await ctx.db.commit()
    return await _entry_out(ctx, entry)


async def reverse_entry(ctx: Ctx, entry_id: uuid.UUID) -> EntryOut:
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    entry = await ctx.db.scalar(select(JournalEntry).where(JournalEntry.id == entry_id).with_for_update())
    if entry is None:
        raise NotFound()
    if entry.reversed_by:
        raise Conflict("This entry was already reversed.", code="already_reversed")
    lines = list(await ctx.db.scalars(select(JournalLine).where(JournalLine.entry_id == entry.id)))
    legs = [
        postings.Leg(
            line.account_id, line.debit - line.credit, line.description, line.tax_rate_id, line.tax_base
        )
        for line in lines
    ]
    reversal = await write(
        ctx.db,
        postings.Posting(f"Reversal of #{entry.number}", postings.reverse(legs)),
        today(ctx.tenant.timezone),
        user_id=ctx.user.id,
    )
    assert reversal is not None
    entry.reversed_by = reversal.id
    await audit.record(
        ctx.db,
        "accounting.entry_reversed",
        target_type="journal_entry",
        target_id=entry.id,
        data={"number": entry.number},
    )
    await ctx.db.commit()
    return await _entry_out(ctx, reversal)


# ---- Reports --------------------------------------------------------------------------


async def _sums(
    ctx: Ctx, *, start: date | None = None, end: date | None = None
) -> dict[uuid.UUID, tuple[int, int]]:
    query = (
        select(JournalLine.account_id, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(
            JournalEntry,
            (JournalEntry.tenant_id == JournalLine.tenant_id) & (JournalEntry.id == JournalLine.entry_id),
        )
        .group_by(JournalLine.account_id)
    )
    if start:
        query = query.where(JournalEntry.entry_date >= start)
    if end:
        query = query.where(JournalEntry.entry_date <= end)
    return {a: (int(d or 0), int(c or 0)) for a, d, c in (await ctx.db.execute(query)).all()}


def _natural(kind: str, debit: int, credit: int) -> int:
    """The balance as people read it: assets and expenses debit-positive, the rest credit-positive."""
    return debit - credit if kind in DEBIT_NORMAL else credit - debit


async def trial_balance(ctx: Ctx, as_of: date) -> TrialBalanceOut:
    ctx.require(access.VIEW)
    sums = await _sums(ctx, end=as_of)
    rows = []
    for a in await ctx.db.scalars(select(Account).order_by(Account.code)):
        d, c = sums.get(a.id, (0, 0))
        if d or c:
            net = d - c
            rows.append(
                ReportRow(
                    account_id=a.id,
                    code=a.code,
                    name=a.name,
                    type=a.type,
                    debit=max(net, 0),
                    credit=max(-net, 0),
                )
            )
    return TrialBalanceOut(
        as_of=as_of, rows=rows, debit=sum(r.debit for r in rows), credit=sum(r.credit for r in rows)
    )


async def profit_and_loss(ctx: Ctx, start: date, end: date) -> ProfitLossOut:
    ctx.require(access.VIEW)
    sums = await _sums(ctx, start=start, end=end)
    income: list[ReportRow] = []
    expenses: list[ReportRow] = []
    for a in await ctx.db.scalars(
        select(Account).where(Account.type.in_(("income", "expense"))).order_by(Account.code)
    ):
        d, c = sums.get(a.id, (0, 0))
        if not (d or c):
            continue
        row = ReportRow(
            account_id=a.id,
            code=a.code,
            name=a.name,
            type=a.type,
            debit=d,
            credit=c,
            amount=_natural(a.type, d, c),
        )
        (income if a.type == "income" else expenses).append(row)
    total_income = sum(r.amount for r in income)
    total_expenses = sum(r.amount for r in expenses)
    return ProfitLossOut(
        start=start,
        end=end,
        income=income,
        expenses=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        profit=total_income - total_expenses,
    )


async def balance_sheet(ctx: Ctx, as_of: date) -> BalanceSheetOut:
    ctx.require(access.VIEW)
    sums = await _sums(ctx, end=as_of)
    groups: dict[str, list[ReportRow]] = defaultdict(list)
    earnings = 0
    for a in await ctx.db.scalars(select(Account).order_by(Account.code)):
        d, c = sums.get(a.id, (0, 0))
        if not (d or c):
            continue
        if a.type in ("income", "expense"):
            earnings += c - d
            continue
        groups[a.type].append(
            ReportRow(
                account_id=a.id,
                code=a.code,
                name=a.name,
                type=a.type,
                debit=d,
                credit=c,
                amount=_natural(a.type, d, c),
            )
        )
    assets = sum(r.amount for r in groups["asset"])
    liabilities = sum(r.amount for r in groups["liability"])
    equity = sum(r.amount for r in groups["equity"]) + earnings
    return BalanceSheetOut(
        as_of=as_of,
        assets=groups["asset"],
        liabilities=groups["liability"],
        equity=groups["equity"],
        earnings=earnings,
        total_assets=assets,
        total_liabilities=liabilities,
        total_equity=equity,
        balanced=assets == liabilities + equity,
    )


async def ledger(ctx: Ctx, account_ids: list[uuid.UUID], start: date, end: date) -> LedgerOut:
    ctx.require(access.VIEW)
    accounts_ = list(await ctx.db.scalars(select(Account).where(Account.id.in_(account_ids))))
    if not accounts_:
        raise NotFound()
    kind = accounts_[0].type
    opening_sums = await _sums(ctx, end=start - timedelta(days=1))
    opening = sum(_natural(kind, *opening_sums.get(a.id, (0, 0))) for a in accounts_)
    rows = (
        await ctx.db.execute(
            select(JournalLine, JournalEntry)
            .join(
                JournalEntry,
                (JournalEntry.tenant_id == JournalLine.tenant_id) & (JournalEntry.id == JournalLine.entry_id),
            )
            .where(
                JournalLine.account_id.in_(account_ids),
                JournalEntry.entry_date >= start,
                JournalEntry.entry_date <= end,
            )
            .order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.position)
        )
    ).all()
    running = opening
    out = []
    for line, entry in rows:
        running += _natural(kind, line.debit, line.credit)
        out.append(
            LedgerRow(
                entry_id=entry.id,
                number=entry.number,
                entry_date=entry.entry_date,
                memo=entry.memo,
                debit=line.debit,
                credit=line.credit,
                balance=running,
            )
        )
    return LedgerOut(
        accounts=[_account_out(a) for a in accounts_],
        start=start,
        end=end,
        opening=opening,
        rows=out,
        closing=running,
    )


async def cash_book(ctx: Ctx, start: date, end: date) -> LedgerOut:
    ids = list(await ctx.db.scalars(select(Account.id).where(Account.role.in_(CASH_ROLES))))
    return await ledger(ctx, ids, start, end)


# ---- Tax returns ----------------------------------------------------------------------


def _template_out(t: TaxReturnTemplate) -> TemplateOut:
    return TemplateOut(id=t.id, name=t.name, boxes=t.boxes or [], note=t.note, version=t.version)


async def templates(ctx: Ctx) -> list[TemplateOut]:
    ctx.require(access.VIEW)
    return [
        _template_out(t)
        for t in await ctx.db.scalars(select(TaxReturnTemplate).order_by(TaxReturnTemplate.name))
    ]


async def save_template(ctx: Ctx, body: TemplateIn, template_id: uuid.UUID | None = None) -> TemplateOut:
    ctx.require(access.MANAGE)
    codes = [b.code for b in body.boxes]
    if len(set(codes)) != len(codes):
        raise Invalid(errors=[{"field": "boxes", "message": "Each box needs its own code."}])
    for b in body.boxes:
        for s in b.sources:
            if s.kind == "boxes" and any(str(x) not in codes[: codes.index(b.code)] for x in s.ids):
                raise Invalid(
                    errors=[{"field": "boxes", "message": f"Box {b.code} can only add up boxes above it."}]
                )
    if template_id:
        row = await ctx.db.get(TaxReturnTemplate, template_id)
        if row is None:
            raise NotFound()
    else:
        row = TaxReturnTemplate()
        ctx.db.add(row)
    row.name = body.name
    row.note = body.note
    row.boxes = [b.model_dump(mode="json") for b in body.boxes]
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "accounting.tax_template_saved",
        target_type="tax_return_template",
        target_id=row.id,
        data={"name": row.name},
    )
    await ctx.db.commit()
    return _template_out(row)


async def tax_return(ctx: Ctx, template_id: uuid.UUID, start: date, end: date) -> TaxReturnOut:
    """Fill a return's boxes for a period from the books."""
    ctx.require(access.VIEW)
    template = await ctx.db.get(TaxReturnTemplate, template_id)
    if template is None:
        raise NotFound()
    period = (
        select(JournalLine, Account.type)
        .join(
            JournalEntry,
            (JournalEntry.tenant_id == JournalLine.tenant_id) & (JournalEntry.id == JournalLine.entry_id),
        )
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.entry_date >= start, JournalEntry.entry_date <= end)
    )
    lines = (await ctx.db.execute(period)).all()
    results: dict[str, int] = {}
    boxes = []
    for box in template.boxes or []:
        total = 0
        for source in box.get("sources", []):
            ids = {str(i) for i in source.get("ids", [])}
            sign = int(source.get("sign", 1))
            kind = source.get("kind")
            value = 0
            if kind == "boxes":
                value = sum(results.get(i, 0) for i in ids)
            else:
                for line, account_type in lines:
                    if kind in ("tax_amount", "tax_base"):
                        if line.tax_rate_id is None or str(line.tax_rate_id) not in ids:
                            continue
                        # Output tax (on sales) sits in liability accounts; input tax (on
                        # purchases) in asset accounts. Returns come through as negatives.
                        side = "output" if account_type == "liability" else "input"
                        if source.get("side", "output") != side:
                            continue
                        if kind == "tax_amount":
                            value += (
                                line.credit - line.debit if side == "output" else line.debit - line.credit
                            )
                        else:
                            value += -(line.tax_base or 0) if side == "output" else line.tax_base or 0
                    elif kind == "account" and str(line.account_id) in ids:
                        value += _natural(account_type, line.debit, line.credit)
            total += sign * value
        results[str(box["code"])] = total
        boxes.append(BoxOut(code=str(box["code"]), label=str(box.get("label", "")), amount=total))
    return TaxReturnOut(template_id=template.id, name=template.name, start=start, end=end, boxes=boxes)
