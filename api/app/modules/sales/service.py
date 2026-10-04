"""Selling: the catalogue, taxes, the cash drawer, sales, returns, voids, receipts and the
period's figures (including tax totals the workspace's accountant files from)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.time import utcnow
from app.modules.customers import service as customers
from app.modules.customers.models import Customer
from app.modules.expenses import service as expenses
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Branch, Tenant, User
from app.modules.sales import access, tax
from app.modules.sales.models import (
    CashSession,
    Product,
    ProductCategory,
    Sale,
    SaleLine,
    ShopSettings,
    TaxRate,
)
from app.modules.sales.schemas import (
    CategoryIn,
    CategoryOut,
    CloseIn,
    DayTotal,
    LineIn,
    LineOut,
    LineTaxOut,
    OpenIn,
    ProductIn,
    ProductOut,
    ProductPatch,
    ProductTotal,
    ReceiptOut,
    ReturnIn,
    SaleIn,
    SaleOut,
    SellerTotal,
    SessionOut,
    ShopSettingsIn,
    ShopSettingsOut,
    SummaryOut,
    TaxRateIn,
    TaxRateOut,
    TaxSummary,
    VoidIn,
)

OFFLINE_DAYS = 7
MAX_SUMMARY_DAYS = 366


# ---- Settings and taxes ---------------------------------------------------------------


async def _settings(db: AsyncSession, *, lock: bool = False) -> ShopSettings:
    query = select(ShopSettings)
    if lock:
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        row = ShopSettings(prices_include_tax=True, cash_rounding=1, next_number=1)
        db.add(row)
        await db.flush()
        if lock:
            row = await db.scalar(select(ShopSettings).with_for_update()) or row
    return row


def _settings_out(r: ShopSettings) -> ShopSettingsOut:
    return ShopSettingsOut(
        prices_include_tax=r.prices_include_tax,
        cash_rounding=r.cash_rounding,
        tax_id_label=r.tax_id_label,
        tax_id=r.tax_id,
        receipt_header=r.receipt_header,
        receipt_footer=r.receipt_footer,
        version=r.version,
    )


async def get_settings(ctx: Ctx) -> ShopSettingsOut:
    ctx.require(access.SELL)
    return _settings_out(await _settings(ctx.db))


async def save_settings(ctx: Ctx, body: ShopSettingsIn) -> ShopSettingsOut:
    ctx.require(access.MANAGE)
    row = await _settings(ctx.db, lock=True)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    await audit.record(ctx.db, "sales.settings_changed", target_type="workspace", data=body.model_dump())
    await ctx.db.commit()
    return _settings_out(row)


def _rate_out(r: TaxRate) -> TaxRateOut:
    return TaxRateOut(
        id=r.id,
        name=r.name,
        code=r.code,
        percent=r.percent,
        compound=r.compound,
        position=r.position,
        active=r.active,
        default=r.default,
        version=r.version,
    )


async def tax_rates(ctx: Ctx) -> list[TaxRateOut]:
    ctx.require(access.SELL)
    rows = await ctx.db.scalars(select(TaxRate).order_by(TaxRate.position, TaxRate.name))
    return [_rate_out(r) for r in rows]


async def save_tax_rate(ctx: Ctx, body: TaxRateIn, rate_id: uuid.UUID | None = None) -> TaxRateOut:
    """Rates are the workspace's own: nothing is assumed about any country."""
    ctx.require(access.MANAGE)
    if rate_id:
        row = await ctx.db.get(TaxRate, rate_id)
        if row is None:
            raise NotFound()
        before = _rate_out(row).model_dump(mode="json")
        for k, v in body.model_dump().items():
            setattr(row, k, v)
    else:
        before = None
        row = TaxRate(**body.model_dump())
        ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "sales.tax_rate_saved",
        target_type="tax_rate",
        target_id=row.id,
        data={"before": before, "after": _rate_out(row).model_dump(mode="json")},
    )
    await ctx.db.commit()
    return _rate_out(row)


async def _rates(db: AsyncSession, ids: Sequence[uuid.UUID] | None) -> list[TaxRate]:
    """The rates for a line, in order; None means the workspace's default rates."""
    query = select(TaxRate).order_by(TaxRate.position, TaxRate.name)
    if ids is None:
        query = query.where(TaxRate.default.is_(True), TaxRate.active.is_(True))
    elif not ids:
        return []
    else:
        query = query.where(TaxRate.id.in_(ids))
    return list(await db.scalars(query))


# ---- Catalogue ------------------------------------------------------------------------


def _product_out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        code=p.code,
        category_id=p.category_id,
        price=p.price,
        tax_rate_ids=list(p.tax_rate_ids or []),
        unit=p.unit,
        favorite=p.favorite,
        active=p.active,
        position=p.position,
        version=p.version,
    )


async def products(ctx: Ctx, *, include_inactive: bool = False, q: str | None = None) -> list[ProductOut]:
    ctx.require(access.SELL)
    query = select(Product)
    if not include_inactive:
        query = query.where(Product.active.is_(True))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(Product.name.ilike(like) | Product.code.ilike(like))
    rows = await ctx.db.scalars(
        query.order_by(Product.favorite.desc(), Product.position, Product.name).limit(2000)
    )
    return [_product_out(p) for p in rows]


async def _check_product(ctx: Ctx, category_id: uuid.UUID | None, rate_ids: list[uuid.UUID] | None) -> None:
    if category_id and await ctx.db.get(ProductCategory, category_id) is None:
        raise Invalid(errors=[{"field": "category_id", "message": "Choose a category from the list."}])
    if rate_ids:
        found = set(await ctx.db.scalars(select(TaxRate.id).where(TaxRate.id.in_(rate_ids))))
        if found != set(rate_ids):
            raise Invalid(errors=[{"field": "tax_rate_ids", "message": "Choose taxes from the list."}])


async def create_product(ctx: Ctx, body: ProductIn) -> ProductOut:
    ctx.require(access.MANAGE)
    await _check_product(ctx, body.category_id, body.tax_rate_ids)
    data = body.model_dump()
    if data["tax_rate_ids"] is None:
        data["tax_rate_ids"] = [r.id for r in await _rates(ctx.db, None)]
    row = Product(**data)
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "sales.product_created",
        target_type="product",
        target_id=row.id,
        data={"name": row.name, "price": row.price},
    )
    await ctx.db.commit()
    return _product_out(row)


async def update_product(ctx: Ctx, product_id: uuid.UUID, body: ProductPatch) -> ProductOut:
    ctx.require(access.MANAGE)
    row = await ctx.db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if row is None:
        raise NotFound()
    await _check_product(ctx, body.category_id, body.tax_rate_ids)
    before = {"price": row.price, "tax_rate_ids": [str(i) for i in row.tax_rate_ids or []]}
    for field in body.model_fields_set:
        value = getattr(body, field)
        if value is None and field not in ("code", "category_id"):
            continue
        setattr(row, field, value)
    await audit.record(
        ctx.db,
        "sales.product_changed",
        target_type="product",
        target_id=row.id,
        data={
            "before": before,
            "after": {"price": row.price, "tax_rate_ids": [str(i) for i in row.tax_rate_ids or []]},
        },
    )
    await ctx.db.commit()
    return _product_out(row)


async def categories(ctx: Ctx) -> list[CategoryOut]:
    ctx.require(access.SELL)
    rows = await ctx.db.scalars(
        select(ProductCategory).order_by(ProductCategory.position, ProductCategory.name)
    )
    return [CategoryOut(id=r.id, name=r.name, color=r.color, position=r.position) for r in rows]


async def save_category(ctx: Ctx, body: CategoryIn, category_id: uuid.UUID | None = None) -> CategoryOut:
    ctx.require(access.MANAGE)
    if category_id:
        row = await ctx.db.get(ProductCategory, category_id)
        if row is None:
            raise NotFound()
        for k, v in body.model_dump().items():
            setattr(row, k, v)
    else:
        row = ProductCategory(**body.model_dump())
        ctx.db.add(row)
    await ctx.db.flush()
    await ctx.db.commit()
    return CategoryOut(id=row.id, name=row.name, color=row.color, position=row.position)


# ---- Cash drawer ----------------------------------------------------------------------


async def _open_session(db: AsyncSession, user_id: uuid.UUID) -> CashSession | None:
    return await db.scalar(
        select(CashSession).where(CashSession.opened_by == user_id, CashSession.closed_at.is_(None))
    )


async def _session_totals(db: AsyncSession, s: CashSession) -> tuple[int, int, int, int]:
    """Cash taken, cash given back, cash spent from the drawer, and the number of sales."""
    rows = (
        await db.execute(
            select(Sale.kind, func.coalesce(func.sum(Sale.paid_cash - Sale.change), 0), func.count())
            .where(Sale.session_id == s.id, Sale.status == "completed")
            .group_by(Sale.kind)
        )
    ).all()
    by = {k: (int(c), int(n)) for k, c, n in rows}
    taken = by.get("sale", (0, 0))[0]
    refunded = -by.get("return", (0, 0))[0]
    spent = await expenses.drawer_expenses(db, s.opened_by, s.opened_at, s.closed_at)
    return taken, refunded, spent, by.get("sale", (0, 0))[1]


async def _session_out(db: AsyncSession, s: CashSession) -> SessionOut:
    taken, refunded, spent, count = await _session_totals(db, s)
    expected = s.opening_float + taken - refunded - spent if s.expected_cash is None else s.expected_cash
    name = await db.scalar(select(User.name).where(User.id == s.opened_by))
    return SessionOut(
        id=s.id,
        branch_id=s.branch_id,
        opened_by_name=name,
        opened_at=s.opened_at,
        opening_float=s.opening_float,
        closed_at=s.closed_at,
        cash_sales=taken,
        cash_refunds=refunded,
        cash_expenses=spent,
        expected_cash=expected,
        counted_cash=s.counted_cash,
        difference=None if s.counted_cash is None else s.counted_cash - expected,
        sales_count=count,
        note=s.note,
    )


async def current_session(ctx: Ctx) -> SessionOut | None:
    ctx.require(access.SELL)
    found = await _open_session(ctx.db, ctx.user.id)
    return await _session_out(ctx.db, found) if found else None


async def open_session(ctx: Ctx, body: OpenIn) -> SessionOut:
    ctx.require(access.SELL)
    if await _open_session(ctx.db, ctx.user.id):
        raise Conflict("Your cash drawer is already open.", code="drawer_open")
    if body.branch_id and await ctx.db.get(Branch, body.branch_id) is None:
        raise Invalid(errors=[{"field": "branch_id", "message": "Choose a branch from the list."}])
    row = CashSession(
        branch_id=body.branch_id,
        opened_by=ctx.user.id,
        opened_at=utcnow(),
        opening_float=body.opening_float,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "sales.drawer_opened",
        target_type="cash_session",
        target_id=row.id,
        data={"float": row.opening_float},
    )
    await ctx.db.commit()
    return await _session_out(ctx.db, row)


async def close_session(ctx: Ctx, body: CloseIn) -> SessionOut:
    ctx.require(access.SELL)
    row = await _open_session(ctx.db, ctx.user.id)
    if row is None:
        raise Conflict("Your cash drawer isn't open.", code="drawer_closed")
    taken, refunded, spent, _ = await _session_totals(ctx.db, row)
    row.closed_at = utcnow()
    row.closed_by = ctx.user.id
    row.expected_cash = row.opening_float + taken - refunded - spent
    row.counted_cash = body.counted_cash
    row.note = body.note
    await audit.record(
        ctx.db,
        "sales.drawer_closed",
        target_type="cash_session",
        target_id=row.id,
        data={"expected": row.expected_cash, "counted": row.counted_cash},
    )
    await events.emit(
        ctx.db,
        "sales.drawer_closed",
        subject_type="cash_session",
        subject_id=row.id,
        data={
            "expected": row.expected_cash,
            "counted": row.counted_cash,
            "difference": row.counted_cash - row.expected_cash,
        },
    )
    await ctx.db.commit()
    return await _session_out(ctx.db, row)


async def sessions(ctx: Ctx, *, limit: int = 60) -> list[SessionOut]:
    ctx.require(access.VIEW)
    rows = await ctx.db.scalars(select(CashSession).order_by(CashSession.opened_at.desc()).limit(limit))
    return [await _session_out(ctx.db, s) for s in rows]


# ---- Selling --------------------------------------------------------------------------


def _money(quantity: Decimal, unit_price: int) -> int:
    return int((quantity * unit_price).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _rate(r: TaxRate) -> tax.Rate:
    return tax.Rate(id=str(r.id), name=r.name, percent=Decimal(r.percent), compound=r.compound)


async def _priced_line(
    ctx: Ctx, line: LineIn, position: int, inclusive: bool, products: dict[uuid.UUID, Product]
) -> SaleLine:
    if line.product_id:
        product = products.get(line.product_id)
        if product is None:
            raise Invalid(
                errors=[
                    {"field": f"lines.{position}.product_id", "message": "That item isn't in the catalogue."}
                ]
            )
        name = line.name or product.name
        unit_price = product.price
        if line.unit_price is not None and line.unit_price != product.price:
            if not ctx.can(access.MANAGE):
                raise Forbidden("Only someone who manages sales can change a price.", code="price_change")
            unit_price = line.unit_price
        rate_rows = await _rates(ctx.db, list(product.tax_rate_ids or []))
    else:
        if not line.name or line.unit_price is None:
            raise Invalid(
                errors=[{"field": f"lines.{position}", "message": "Give the item a name and a price."}]
            )
        name, unit_price = line.name, line.unit_price
        rate_rows = await _rates(ctx.db, line.tax_rate_ids)
    gross = _money(line.quantity, unit_price)
    if line.discount > gross:
        raise Invalid(
            errors=[
                {"field": f"lines.{position}.discount", "message": "The discount is more than the price."}
            ]
        )
    result = tax.line(gross - line.discount, [_rate(r) for r in rate_rows], inclusive=inclusive)
    codes = {str(r.id): r.code for r in rate_rows}
    return SaleLine(
        position=position,
        product_id=line.product_id,
        name=name,
        quantity=line.quantity,
        unit_price=unit_price,
        discount=line.discount,
        net=result.net,
        tax=sum(t.amount for t in result.taxes),
        total=result.gross,
        taxes=[
            {
                "id": t.id,
                "name": t.name,
                "code": codes.get(t.id),
                "percent": str(t.percent),
                "amount": t.amount,
            }
            for t in result.taxes
        ],
    )


async def _next_number(db: AsyncSession) -> int:
    settings = await _settings(db, lock=True)
    number = settings.next_number
    settings.next_number = number + 1
    return number


async def _by_client(db: AsyncSession, client_id: uuid.UUID) -> Sale | None:
    return await db.scalar(select(Sale).where(Sale.client_id == client_id))


def _when(ctx: Ctx, sold_at: datetime | None) -> datetime:
    now = utcnow()
    if sold_at is None:
        return now
    if sold_at.tzinfo is None:
        raise Invalid(errors=[{"field": "sold_at", "message": "Include the time zone."}])
    if sold_at > now + timedelta(minutes=5) or sold_at < now - timedelta(days=OFFLINE_DAYS):
        raise Invalid(errors=[{"field": "sold_at", "message": "That time is too far from now."}])
    return sold_at


async def _session_for(ctx: Ctx, when: datetime) -> CashSession:
    """The seller's open drawer; for a sale made offline, the drawer that was open then."""
    found = await _open_session(ctx.db, ctx.user.id)
    if found is not None:
        return found
    earlier = await ctx.db.scalar(
        select(CashSession)
        .where(
            CashSession.opened_by == ctx.user.id, CashSession.opened_at <= when, CashSession.closed_at >= when
        )
        .order_by(CashSession.opened_at.desc())
    )
    if earlier is None:
        raise Conflict("Open the cash drawer first.", code="drawer_closed")
    return earlier


async def sell(ctx: Ctx, body: SaleIn) -> tuple[SaleOut, bool]:
    """Record a sale. Returns it and whether it's new (False: this till already sent it)."""
    ctx.require(access.SELL)
    if existing := await _by_client(ctx.db, body.client_id):
        return await sale_out(ctx, existing), False
    when = _when(ctx, body.sold_at)
    session = await _session_for(ctx, when)
    if body.customer_id is not None:
        if ctx.entitlements is None or "customers" not in ctx.entitlements.modules:
            raise Invalid("Switch on Customers & dues to sell on credit.", code="customers_off")
        await customers.customer(ctx, body.customer_id)
    settings = await _settings(ctx.db)
    wanted = {line.product_id for line in body.lines if line.product_id}
    catalogue = (
        {p.id: p for p in await ctx.db.scalars(select(Product).where(Product.id.in_(wanted)))}
        if wanted
        else {}
    )
    lines = [
        await _priced_line(ctx, line, i, settings.prices_include_tax, catalogue)
        for i, line in enumerate(body.lines)
    ]
    net = sum(line.net for line in lines)
    tax_total = sum(line.tax for line in lines)
    gross = sum(line.total for line in lines)
    rounding = 0 if body.customer_id else tax.cash_round(gross, settings.cash_rounding) - gross
    total = gross + rounding
    if body.customer_id:
        paid = min(body.paid_cash, total)
        on_account = total - paid
        change = body.paid_cash - paid
    else:
        if body.paid_cash < total:
            raise Invalid(
                errors=[{"field": "paid_cash", "message": "The cash given is less than the total."}]
            )
        paid, on_account, change = body.paid_cash, 0, body.paid_cash - total
    row = Sale(
        number=await _next_number(ctx.db),
        client_id=body.client_id,
        kind="sale",
        status="completed",
        session_id=session.id,
        branch_id=session.branch_id,
        sold_by=ctx.user.id,
        sold_at=when,
        customer_id=body.customer_id,
        net=net,
        tax=tax_total,
        rounding=rounding,
        total=total,
        paid_cash=body.paid_cash if not body.customer_id else paid + change,
        change=change,
        on_account=on_account,
        prices_include_tax=settings.prices_include_tax,
        note=body.note,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    for line in lines:
        line.sale_id = row.id
    ctx.db.add_all(lines)
    if body.customer_id and on_account:
        await customers.post(ctx, body.customer_id, "sale", on_account, sale_id=row.id, check_limit=True)
    await events.emit(
        ctx.db,
        "sale.completed",
        subject_type="sale",
        subject_id=row.id,
        data={
            "number": row.number,
            "total": row.total,
            "on_account": on_account,
            "customer_id": body.customer_id,
        },
    )
    try:
        await ctx.db.commit()
    except IntegrityError:
        # The same sale arrived twice at once; keep the first.
        await ctx.db.rollback()
        if existing := await _by_client(ctx.db, body.client_id):
            return await sale_out(ctx, existing), False
        raise
    return await sale_out(ctx, row), True


async def _returned(db: AsyncSession, line_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not line_ids:
        return {}
    rows = (
        await db.execute(
            select(SaleLine.returned_line_id, func.sum(SaleLine.quantity))
            .join(Sale, (Sale.tenant_id == SaleLine.tenant_id) & (Sale.id == SaleLine.sale_id))
            .where(SaleLine.returned_line_id.in_(line_ids), Sale.status == "completed")
            .group_by(SaleLine.returned_line_id)
        )
    ).all()
    return {lid: Decimal(q) for lid, q in rows if lid}


def _share(amount: int, part: Decimal, whole: Decimal) -> int:
    return int((Decimal(amount) * part / whole).quantize(Decimal(1), rounding=ROUND_HALF_UP))


async def return_items(ctx: Ctx, sale_id: uuid.UUID, body: ReturnIn) -> SaleOut:
    """Take items back: a negative sale, refunded in cash or to the customer's account."""
    ctx.require(access.MANAGE)
    if existing := await _by_client(ctx.db, body.client_id):
        return await sale_out(ctx, existing)
    original = await ctx.db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if original is None:
        raise NotFound()
    if original.kind != "sale" or original.status != "completed":
        raise Conflict("Only completed sales can be returned.", code="not_returnable")
    if body.to_account and not original.customer_id:
        raise Invalid("This sale wasn't to a customer.", code="no_customer")
    lines = {
        line.id: line for line in await ctx.db.scalars(select(SaleLine).where(SaleLine.sale_id == sale_id))
    }
    already = await _returned(ctx.db, list(lines))
    back: list[SaleLine] = []
    for i, item in enumerate(body.lines):
        line = lines.get(item.line_id)
        if line is None:
            raise Invalid(
                errors=[{"field": f"lines.{i}.line_id", "message": "That line isn't on this sale."}]
            )
        left = Decimal(line.quantity) - already.get(line.id, Decimal(0))
        if item.quantity > left:
            raise Invalid(
                errors=[{"field": f"lines.{i}.quantity", "message": f"Only {left} can still be returned."}]
            )
        whole = Decimal(line.quantity)
        taxes = [{**t, "amount": -_share(int(t["amount"]), item.quantity, whole)} for t in line.taxes or []]
        back.append(
            SaleLine(
                position=i,
                product_id=line.product_id,
                name=line.name,
                quantity=item.quantity,
                unit_price=line.unit_price,
                discount=-_share(line.discount, item.quantity, whole),
                net=-_share(line.net, item.quantity, whole),
                tax=sum(int(t["amount"]) for t in taxes),
                total=-_share(line.total, item.quantity, whole),
                taxes=taxes,
                returned_line_id=line.id,
            )
        )
    total = sum(line.total for line in back)
    refund_cash = 0 if body.to_account else -total
    session = None
    if refund_cash:
        session = await _open_session(ctx.db, ctx.user.id)
        if session is None:
            raise Conflict("Open the cash drawer to give cash back.", code="drawer_closed")
    row = Sale(
        number=await _next_number(ctx.db),
        client_id=body.client_id,
        kind="return",
        status="completed",
        original_id=original.id,
        session_id=session.id if session else None,
        branch_id=original.branch_id,
        sold_by=ctx.user.id,
        sold_at=utcnow(),
        customer_id=original.customer_id,
        net=sum(line.net for line in back),
        tax=sum(line.tax for line in back),
        rounding=0,
        total=total,
        paid_cash=-refund_cash,
        change=0,
        on_account=total if body.to_account else 0,
        prices_include_tax=original.prices_include_tax,
        note=body.note,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    for line in back:
        line.sale_id = row.id
    ctx.db.add_all(back)
    if body.to_account and original.customer_id:
        await customers.post(
            ctx, original.customer_id, "return", total, sale_id=row.id, note=f"Return of #{original.number}"
        )
    await audit.record(
        ctx.db,
        "sales.returned",
        target_type="sale",
        target_id=original.id,
        data={"return": str(row.id), "total": total},
    )
    await ctx.db.commit()
    return await sale_out(ctx, row)


async def void(ctx: Ctx, sale_id: uuid.UUID, body: VoidIn) -> SaleOut:
    """Cancel a sale entered by mistake (it stays on record, marked void)."""
    ctx.require(access.MANAGE)
    row = await ctx.db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
    if row is None:
        raise NotFound()
    if row.status != "completed":
        raise Conflict("This sale is already void.", code="already_void")
    if row.kind == "sale" and await _returned(
        ctx.db, list(await ctx.db.scalars(select(SaleLine.id).where(SaleLine.sale_id == row.id)))
    ):
        raise Conflict("Items from this sale were returned; void the return first.", code="has_returns")
    row.status = "voided"
    row.voided_by = ctx.user.id
    row.voided_at = utcnow()
    row.void_reason = body.reason
    if row.customer_id and row.on_account:
        await customers.post(
            ctx, row.customer_id, "adjustment", -row.on_account, sale_id=row.id, note=f"Void of #{row.number}"
        )
    await audit.record(
        ctx.db,
        "sales.voided",
        target_type="sale",
        target_id=row.id,
        data={"number": row.number, "reason": body.reason},
    )
    await ctx.db.commit()
    return await sale_out(ctx, row)


# ---- Reading --------------------------------------------------------------------------


async def sale_out(ctx: Ctx, s: Sale) -> SaleOut:
    lines = list(
        await ctx.db.scalars(select(SaleLine).where(SaleLine.sale_id == s.id).order_by(SaleLine.position))
    )
    returned = await _returned(ctx.db, [line.id for line in lines]) if s.kind == "sale" else {}
    seller = await ctx.db.scalar(select(User.name).where(User.id == s.sold_by))
    customer = await ctx.db.get(Customer, s.customer_id) if s.customer_id else None
    return SaleOut(
        id=s.id,
        number=s.number,
        kind=s.kind,
        status=s.status,
        original_id=s.original_id,
        sold_at=s.sold_at,
        sold_by_name=seller,
        customer_id=s.customer_id,
        customer_name=customer.name if customer else None,
        net=s.net,
        tax=s.tax,
        rounding=s.rounding,
        total=s.total,
        paid_cash=s.paid_cash,
        change=s.change,
        on_account=s.on_account,
        prices_include_tax=s.prices_include_tax,
        note=s.note,
        void_reason=s.void_reason,
        lines=[
            LineOut(
                id=line.id,
                product_id=line.product_id,
                name=line.name,
                quantity=Decimal(line.quantity),
                unit_price=line.unit_price,
                discount=line.discount,
                net=line.net,
                tax=line.tax,
                total=line.total,
                taxes=[LineTaxOut(**t) for t in line.taxes or []],
                returned=returned.get(line.id, Decimal(0)),
            )
            for line in lines
        ],
    )


async def _visible(ctx: Ctx) -> Any:
    """Sellers see their own sales; people with sales.view see all."""
    return True if ctx.can(access.VIEW) else Sale.sold_by == ctx.user.id


async def get_sale(ctx: Ctx, sale_id: uuid.UUID) -> SaleOut:
    ctx.require(access.SELL)
    row = await ctx.db.scalar(select(Sale).where(Sale.id == sale_id, await _visible(ctx)))
    if row is None:
        raise NotFound()
    return await sale_out(ctx, row)


async def list_sales(
    ctx: Ctx, *, day: date | None = None, customer_id: uuid.UUID | None = None, limit: int = 100
) -> list[SaleOut]:
    ctx.require(access.SELL)
    assert ctx.tenant is not None
    query = select(Sale).where(await _visible(ctx))
    if day is not None:
        start, end = _day_bounds(ctx.tenant.timezone, day, day)
        query = query.where(Sale.sold_at >= start, Sale.sold_at < end)
    if customer_id is not None:
        query = query.where(Sale.customer_id == customer_id)
    rows = await ctx.db.scalars(query.order_by(Sale.sold_at.desc()).limit(min(limit, 500)))
    return [await sale_out(ctx, s) for s in rows]


def _day_bounds(timezone: str, start: date, end: date) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    return datetime.combine(start, time(0), zone), datetime.combine(end + timedelta(days=1), time(0), zone)


def _tax_summary(lines: Sequence[SaleLine]) -> list[TaxSummary]:
    totals: dict[str, dict[str, Any]] = {}
    for line in lines:
        for t in line.taxes or []:
            entry = totals.setdefault(
                t["id"],
                {
                    "id": t["id"],
                    "name": t["name"],
                    "code": t.get("code"),
                    "percent": Decimal(str(t["percent"])),
                    "taxable": 0,
                    "amount": 0,
                },
            )
            entry["taxable"] += line.net
            entry["amount"] += int(t["amount"])
    return [TaxSummary(**v) for v in sorted(totals.values(), key=lambda v: (v["name"], v["percent"]))]


async def receipt(ctx: Ctx, sale_id: uuid.UUID) -> ReceiptOut:
    sale = await get_sale(ctx, sale_id)
    assert ctx.tenant is not None
    settings = await _settings(ctx.db)
    row = await ctx.db.get(Sale, sale_id)
    branch = await ctx.db.get(Branch, row.branch_id) if row and row.branch_id else None
    lines = list(await ctx.db.scalars(select(SaleLine).where(SaleLine.sale_id == sale_id)))
    return ReceiptOut(
        sale=sale,
        shop_name=ctx.tenant.name,
        branch_name=branch.name if branch else None,
        branch_address=getattr(branch, "address", None) if branch else None,
        tax_id_label=settings.tax_id_label,
        tax_id=settings.tax_id,
        header=settings.receipt_header,
        footer=settings.receipt_footer,
        currency=ctx.tenant.currency,
        taxes=_tax_summary(lines),
    )


async def summary(ctx: Ctx, start: date, end: date) -> SummaryOut:
    """Totals for a period: what the accountant needs for tax returns, and the day's figures."""
    ctx.require(access.VIEW)
    assert ctx.tenant is not None
    if end < start or (end - start).days > MAX_SUMMARY_DAYS:
        raise Invalid(errors=[{"field": "end", "message": "Choose up to a year, ending after it starts."}])
    lo, hi = _day_bounds(ctx.tenant.timezone, start, end)
    sales = list(
        await ctx.db.scalars(
            select(Sale).where(Sale.sold_at >= lo, Sale.sold_at < hi, Sale.status == "completed")
        )
    )
    ids = [s.id for s in sales]
    lines = list(await ctx.db.scalars(select(SaleLine).where(SaleLine.sale_id.in_(ids)))) if ids else []
    names = (
        dict(
            (
                await ctx.db.execute(
                    select(User.id, User.name).where(User.id.in_({s.sold_by for s in sales}))
                )
            ).all()
        )
        if sales
        else {}
    )
    sellers: dict[uuid.UUID, list[int]] = defaultdict(lambda: [0, 0])
    days: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    zone = ZoneInfo(ctx.tenant.timezone)
    for s in sales:
        if s.kind == "sale":
            sellers[s.sold_by][0] += 1
            days[s.sold_at.astimezone(zone).date()][0] += 1
        sellers[s.sold_by][1] += s.total
        days[s.sold_at.astimezone(zone).date()][1] += s.total
    products: dict[str, list[Any]] = defaultdict(lambda: [Decimal(0), 0])
    for line in lines:
        products[line.name][0] += Decimal(line.quantity) if line.total >= 0 else -Decimal(line.quantity)
        products[line.name][1] += line.total
    return SummaryOut(
        start=start,
        end=end,
        count=sum(1 for s in sales if s.kind == "sale"),
        net=sum(s.net for s in sales),
        tax=sum(s.tax for s in sales),
        total=sum(s.total for s in sales),
        cash=sum(s.paid_cash - s.change for s in sales),
        on_account=sum(s.on_account for s in sales),
        returns=-sum(s.total for s in sales if s.kind == "return"),
        taxes=_tax_summary(lines),
        sellers=sorted(
            (SellerTotal(name=names.get(u, "?"), count=c, total=t) for u, (c, t) in sellers.items()),
            key=lambda x: -x.total,
        ),
        products=sorted(
            (ProductTotal(name=n, quantity=q, total=t) for n, (q, t) in products.items()),
            key=lambda x: -x.total,
        )[:20],
        days=[DayTotal(day=d, count=c, total=t) for d, (c, t) in sorted(days.items())],
    )


# ---- Switching the module on ----------------------------------------------------------


async def seed(db: AsyncSession, tenant: Tenant, module: str) -> None:
    """Settings the first time Sales is on. No taxes are assumed: the workspace adds its own."""
    if module != "sales":
        return
    await _settings(db)


def register_hooks() -> None:
    if seed not in hooks.module_enabled:
        hooks.module_enabled.append(seed)
