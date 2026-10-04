"""Stock: every change is a movement; levels and values follow from them.

Stock is tracked for an item once it has opening stock, a purchase or its settings say
so. Sales, returns and voids move it automatically, in the same transaction as the sale.
Each movement also announces its cost value (`stock.moved`) so the books can follow.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, events
from app.core.errors import Invalid, NotFound
from app.core.time import today, utcnow
from app.modules.inventory import access, costing
from app.modules.inventory.models import (
    Purchase,
    StockCount,
    StockItem,
    StockLevel,
    StockMovement,
    Supplier,
    SupplierEntry,
    Transfer,
)
from app.modules.inventory.schemas import (
    ItemSettingsIn,
    LevelOut,
    MovementOut,
    OpeningIn,
    PurchaseIn,
    PurchaseOut,
    StockAdjustmentIn,
    StockCountIn,
    StockCountOut,
    StockOut,
    SupplierIn,
    SupplierOut,
    SupplierPaymentIn,
    TransferIn,
)
from app.modules.platform.deps import Ctx, load_entitlements
from app.modules.platform.models import Branch
from app.modules.sales.models import Product, Sale, SaleLine, TaxRate

NO_BRANCH = uuid.UUID(int=0)


# ---- The ledger -----------------------------------------------------------------------


async def _item(db: AsyncSession, product_id: uuid.UUID, *, create: bool = True) -> StockItem | None:
    row = await db.scalar(select(StockItem).where(StockItem.product_id == product_id).with_for_update())
    if row is None and create:
        row = StockItem(
            product_id=product_id, track=True, quantity=Decimal(0), value=Decimal(0), average_cost=Decimal(0)
        )
        db.add(row)
        await db.flush()
    return row


async def _level(db: AsyncSession, product_id: uuid.UUID, branch_id: uuid.UUID | None) -> StockLevel:
    key = branch_id or NO_BRANCH
    row = await db.scalar(
        select(StockLevel)
        .where(StockLevel.product_id == product_id, StockLevel.branch_key == key)
        .with_for_update()
    )
    if row is None:
        row = StockLevel(product_id=product_id, branch_id=branch_id, branch_key=key, quantity=Decimal(0))
        db.add(row)
        await db.flush()
    return row


async def record(
    db: AsyncSession,
    product_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    kind: str,
    quantity: Decimal,
    *,
    unit_cost: Decimal | None = None,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    note: str | None = None,
    user_id: uuid.UUID | None = None,
    when: datetime | None = None,
) -> StockMovement:
    """One movement. With `unit_cost` it's stock in at that cost (moves the average)."""
    item = await _item(db, product_id)
    assert item is not None
    position = costing.Position(Decimal(item.quantity), Decimal(item.value), Decimal(item.average_cost))
    if unit_cost is not None:
        position, value = costing.receive(position, quantity, unit_cost)
        cost = unit_cost
    else:
        position, value = costing.move(position, quantity)
        cost = position.average
    item.quantity, item.value, item.average_cost = position.quantity, position.value, position.average
    level = await _level(db, product_id, branch_id)
    level.quantity = Decimal(level.quantity) + quantity
    movement = StockMovement(
        product_id=product_id,
        branch_id=branch_id,
        kind=kind,
        quantity=quantity,
        unit_cost=cost,
        value=value,
        occurred_at=when or utcnow(),
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        created_by=user_id,
    )
    db.add(movement)
    await db.flush()
    await events.emit(
        db,
        "stock.moved",
        subject_type="stock_movement",
        subject_id=movement.id,
        data={
            "kind": kind,
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity": str(quantity),
            "value": costing.money(value),
            "ref_type": ref_type,
            "ref_id": ref_id,
        },
    )
    await _check_low(db, item, level)
    return movement


async def _check_low(db: AsyncSession, item: StockItem, level: StockLevel) -> None:
    if item.reorder_level is None:
        return
    low = Decimal(level.quantity) <= Decimal(item.reorder_level)
    if low and level.low_since is None:
        level.low_since = utcnow()
        name = await db.scalar(select(Product.name).where(Product.id == item.product_id))
        branch = (
            await db.scalar(select(Branch.name).where(Branch.id == level.branch_id))
            if level.branch_id
            else None
        )
        await events.emit(
            db,
            "stock.low",
            subject_type="product",
            subject_id=item.product_id,
            data={
                "title": name,
                "branch": branch,
                "quantity": str(level.quantity),
                "reorder_level": str(item.reorder_level),
            },
        )
    elif not low:
        level.low_since = None


async def _on(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    return "inventory" in (await load_entitlements(db, tenant_id)).modules


async def _tracked(db: AsyncSession, product_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not product_ids:
        return set()
    return set(
        await db.scalars(
            select(StockItem.product_id).where(
                StockItem.product_id.in_(product_ids), StockItem.track.is_(True)
            )
        )
    )


@events.on("sale.completed")
async def _sold(db: AsyncSession, event: events.Event) -> None:
    await _follow_sale(db, event, "sale")


@events.on("sale.returned")
async def _returned(db: AsyncSession, event: events.Event) -> None:
    await _follow_sale(db, event, "return")


async def _follow_sale(db: AsyncSession, event: events.Event, kind: str) -> None:
    """Stock leaves with a sale and comes back with a return (tracked items only)."""
    if not await _on(db, event.tenant_id):
        return
    sale = await db.get(Sale, uuid.UUID(str(event.subject_id)))
    if sale is None:
        return
    lines = list(await db.scalars(select(SaleLine).where(SaleLine.sale_id == sale.id)))
    tracked = await _tracked(db, [line.product_id for line in lines if line.product_id])
    for line in lines:
        if line.product_id not in tracked:
            continue
        quantity = -Decimal(line.quantity) if kind == "sale" else Decimal(line.quantity)
        await record(
            db,
            line.product_id,
            sale.branch_id,
            kind,
            quantity,
            ref_type="sale",
            ref_id=sale.id,
            user_id=sale.sold_by,
            when=sale.sold_at,
        )


@events.on("sale.voided")
async def _voided(db: AsyncSession, event: events.Event) -> None:
    """A void puts back exactly what the sale (or return) moved."""
    if not await _on(db, event.tenant_id):
        return
    sale_id = uuid.UUID(str(event.subject_id))
    moved = list(
        await db.scalars(
            select(StockMovement).where(
                StockMovement.ref_type == "sale",
                StockMovement.ref_id == sale_id,
                StockMovement.kind != "void",
            )
        )
    )
    for m in moved:
        await record(
            db, m.product_id, m.branch_id, "void", -Decimal(m.quantity), ref_type="sale", ref_id=sale_id
        )


# ---- Reading --------------------------------------------------------------------------


async def stock(
    ctx: Ctx, *, branch_id: uuid.UUID | None = None, low_only: bool = False, q: str | None = None
) -> list[StockOut]:
    ctx.require(access.VIEW)
    query = select(Product, StockItem).join(StockItem, StockItem.product_id == Product.id)
    if q:
        query = query.where(Product.name.ilike(f"%{q.strip()}%"))
    rows = (await ctx.db.execute(query.order_by(Product.name).limit(2000))).all()
    levels: dict[uuid.UUID, list[StockLevel]] = {}
    for level in await ctx.db.scalars(
        select(StockLevel).where(StockLevel.product_id.in_([p.id for p, _ in rows]))
    ):
        levels.setdefault(level.product_id, []).append(level)
    out = []
    for product, item in rows:
        mine = [lv for lv in levels.get(product.id, []) if branch_id is None or lv.branch_id == branch_id]
        reorder = Decimal(item.reorder_level) if item.reorder_level is not None else None
        level_out = [
            LevelOut(
                branch_id=lv.branch_id,
                quantity=Decimal(lv.quantity),
                low=reorder is not None and Decimal(lv.quantity) <= reorder,
            )
            for lv in mine
        ]
        quantity = (
            sum((Decimal(lv.quantity) for lv in mine), Decimal(0)) if branch_id else Decimal(item.quantity)
        )
        low = any(lv.low for lv in level_out)
        if low_only and not low:
            continue
        out.append(
            StockOut(
                product_id=product.id,
                name=product.name,
                code=product.code,
                unit=product.unit,
                track=item.track,
                reorder_level=reorder,
                quantity=quantity,
                average_cost=Decimal(item.average_cost),
                value=costing.money(quantity * Decimal(item.average_cost)),
                levels=level_out,
                low=low,
            )
        )
    return out


async def movements(ctx: Ctx, product_id: uuid.UUID, *, limit: int = 200) -> list[MovementOut]:
    ctx.require(access.VIEW)
    rows = await ctx.db.scalars(
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.occurred_at.desc())
        .limit(min(limit, 1000))
    )
    return [
        MovementOut(
            id=m.id,
            product_id=m.product_id,
            branch_id=m.branch_id,
            kind=m.kind,
            quantity=Decimal(m.quantity),
            unit_cost=Decimal(m.unit_cost),
            value=costing.money(Decimal(m.value)),
            occurred_at=m.occurred_at,
            ref_type=m.ref_type,
            ref_id=m.ref_id,
            note=m.note,
        )
        for m in rows
    ]


# ---- Changing stock -------------------------------------------------------------------


async def _product(ctx: Ctx, product_id: uuid.UUID) -> Product:
    product = await ctx.db.get(Product, product_id)
    if product is None:
        raise Invalid(errors=[{"field": "product_id", "message": "That item isn't in the catalogue."}])
    return product


async def _branch(ctx: Ctx, branch_id: uuid.UUID | None, field: str = "branch_id") -> None:
    if branch_id and await ctx.db.get(Branch, branch_id) is None:
        raise Invalid(errors=[{"field": field, "message": "Choose a branch from the list."}])


async def settings(ctx: Ctx, product_id: uuid.UUID, body: ItemSettingsIn) -> StockOut:
    ctx.require(access.MANAGE)
    await _product(ctx, product_id)
    item = await _item(ctx.db, product_id)
    assert item is not None
    item.track = body.track
    item.reorder_level = body.reorder_level
    await ctx.db.commit()
    return next(s for s in await stock(ctx) if s.product_id == product_id)


async def opening(ctx: Ctx, body: OpeningIn) -> StockOut:
    """Stock that was already there when tracking started, at what it cost."""
    ctx.require(access.MANAGE)
    await _product(ctx, body.product_id)
    await _branch(ctx, body.branch_id)
    await record(
        ctx.db,
        body.product_id,
        body.branch_id,
        "opening",
        body.quantity,
        unit_cost=body.unit_cost,
        user_id=ctx.user.id,
    )
    await audit.record(
        ctx.db,
        "inventory.opening",
        target_type="product",
        target_id=body.product_id,
        data={"quantity": str(body.quantity)},
    )
    await ctx.db.commit()
    return next(s for s in await stock(ctx) if s.product_id == body.product_id)


async def adjust(ctx: Ctx, body: StockAdjustmentIn) -> StockOut:
    ctx.require(access.MANAGE)
    if body.quantity == 0:
        raise Invalid(errors=[{"field": "quantity", "message": "Enter how many to add or remove."}])
    await _product(ctx, body.product_id)
    await _branch(ctx, body.branch_id)
    await record(
        ctx.db,
        body.product_id,
        body.branch_id,
        "adjustment",
        body.quantity,
        note=body.reason,
        user_id=ctx.user.id,
    )
    await audit.record(
        ctx.db,
        "inventory.adjusted",
        target_type="product",
        target_id=body.product_id,
        data={"quantity": str(body.quantity), "reason": body.reason},
    )
    await ctx.db.commit()
    return next(s for s in await stock(ctx) if s.product_id == body.product_id)


async def _supplier(ctx: Ctx, supplier_id: uuid.UUID, *, lock: bool = False) -> Supplier:
    query = select(Supplier).where(Supplier.id == supplier_id)
    if lock:
        query = query.with_for_update()
    found = await ctx.db.scalar(query)
    if found is None:
        raise NotFound()
    return found


async def receive(ctx: Ctx, body: PurchaseIn) -> PurchaseOut:
    """Goods in from a supplier: stock up at cost, input tax noted, what's owed recorded."""
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    if body.supplier_id:
        await _supplier(ctx, body.supplier_id, lock=True)
    await _branch(ctx, body.branch_id)
    rates = {
        r.id: r
        for r in await ctx.db.scalars(
            select(TaxRate).where(
                TaxRate.id.in_([line.tax_rate_id for line in body.lines if line.tax_rate_id])
            )
        )
    }
    lines: list[dict[str, Any]] = []
    net = tax = 0
    for i, line in enumerate(body.lines):
        product = await _product(ctx, line.product_id)
        amount = costing.money(line.quantity * line.unit_cost)
        rate = rates.get(line.tax_rate_id) if line.tax_rate_id else None
        if line.tax_rate_id and rate is None:
            raise Invalid(
                errors=[{"field": f"lines.{i}.tax_rate_id", "message": "Choose a tax from the list."}]
            )
        line_tax = costing.money(Decimal(amount) * Decimal(rate.percent) / 100) if rate else 0
        net += amount
        tax += line_tax
        lines.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "quantity": str(line.quantity),
                "unit_cost": str(line.unit_cost),
                "amount": amount,
                "tax_rate_id": str(rate.id) if rate else None,
                "tax_code": rate.code if rate else None,
                "tax": line_tax,
            }
        )
    total = net + tax
    if body.paid > total:
        raise Invalid(errors=[{"field": "paid", "message": "Paid is more than the total."}])
    if not body.supplier_id and body.paid != total:
        raise Invalid(
            errors=[{"field": "paid", "message": "Without a supplier, record the purchase as fully paid."}]
        )
    row = Purchase(
        supplier_id=body.supplier_id,
        branch_id=body.branch_id,
        reference=body.reference,
        received_on=body.received_on or today(ctx.tenant.timezone),
        net=net,
        tax=tax,
        total=total,
        paid=body.paid,
        paid_from=body.paid_from,
        lines=lines,
        note=body.note,
        created_by=ctx.user.id,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    for line in body.lines:
        await record(
            ctx.db,
            line.product_id,
            body.branch_id,
            "purchase",
            line.quantity,
            unit_cost=line.unit_cost,
            ref_type="purchase",
            ref_id=row.id,
            user_id=ctx.user.id,
        )
    if body.supplier_id and total - body.paid:
        ctx.db.add(
            SupplierEntry(
                supplier_id=body.supplier_id,
                kind="purchase",
                amount=total - body.paid,
                occurred_on=row.received_on,
                purchase_id=row.id,
                created_by=ctx.user.id,
            )
        )
    await audit.record(
        ctx.db, "inventory.purchase", target_type="purchase", target_id=row.id, data={"total": total}
    )
    await events.emit(
        ctx.db,
        "purchase.received",
        subject_type="purchase",
        subject_id=row.id,
        data={
            "net": net,
            "tax": tax,
            "total": total,
            "paid": body.paid,
            "paid_from": body.paid_from,
            "supplier_id": body.supplier_id,
            "taxes": [
                {"tax_rate_id": ln["tax_rate_id"], "amount": ln["tax"], "base": ln["amount"]}
                for ln in lines
                if ln["tax_rate_id"]
            ],
        },
    )
    await ctx.db.commit()
    return await purchase(ctx, row.id)


def _purchase_out(p: Purchase, supplier: str | None) -> PurchaseOut:
    return PurchaseOut(
        id=p.id,
        supplier_id=p.supplier_id,
        supplier_name=supplier,
        branch_id=p.branch_id,
        reference=p.reference,
        received_on=p.received_on,
        net=p.net,
        tax=p.tax,
        total=p.total,
        paid=p.paid,
        paid_from=p.paid_from,
        lines=p.lines or [],
        note=p.note,
        created_at=p.created_at,
    )


async def purchase(ctx: Ctx, purchase_id: uuid.UUID) -> PurchaseOut:
    ctx.require(access.VIEW)
    row = await ctx.db.get(Purchase, purchase_id)
    if row is None:
        raise NotFound()
    supplier = await ctx.db.get(Supplier, row.supplier_id) if row.supplier_id else None
    return _purchase_out(row, supplier.name if supplier else None)


async def purchases(ctx: Ctx, *, start: date | None = None, end: date | None = None) -> list[PurchaseOut]:
    ctx.require(access.VIEW)
    query = select(Purchase)
    if start:
        query = query.where(Purchase.received_on >= start)
    if end:
        query = query.where(Purchase.received_on <= end)
    rows = list(
        await ctx.db.scalars(
            query.order_by(Purchase.received_on.desc(), Purchase.created_at.desc()).limit(500)
        )
    )
    names = dict((await ctx.db.execute(select(Supplier.id, Supplier.name))).all())
    return [_purchase_out(p, names.get(p.supplier_id) if p.supplier_id else None) for p in rows]


async def transfer(ctx: Ctx, body: TransferIn) -> None:
    ctx.require(access.MANAGE)
    if body.from_branch_id == body.to_branch_id:
        raise Invalid(errors=[{"field": "to_branch_id", "message": "Choose a different branch to send to."}])
    await _branch(ctx, body.from_branch_id, "from_branch_id")
    await _branch(ctx, body.to_branch_id, "to_branch_id")
    row = Transfer(
        from_branch_id=body.from_branch_id,
        to_branch_id=body.to_branch_id,
        lines=[{"product_id": str(line.product_id), "quantity": str(line.quantity)} for line in body.lines],
        note=body.note,
        created_by=ctx.user.id,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    for line in body.lines:
        await _product(ctx, line.product_id)
        await record(
            ctx.db,
            line.product_id,
            body.from_branch_id,
            "transfer_out",
            -line.quantity,
            ref_type="transfer",
            ref_id=row.id,
            user_id=ctx.user.id,
        )
        await record(
            ctx.db,
            line.product_id,
            body.to_branch_id,
            "transfer_in",
            line.quantity,
            ref_type="transfer",
            ref_id=row.id,
            user_id=ctx.user.id,
        )
    await audit.record(
        ctx.db,
        "inventory.transfer",
        target_type="transfer",
        target_id=row.id,
        data={"lines": len(body.lines)},
    )
    await ctx.db.commit()


async def count(ctx: Ctx, body: StockCountIn) -> StockCountOut:
    """A stock count: differences from what the books say become count movements."""
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    await _branch(ctx, body.branch_id)
    row = StockCount(
        branch_id=body.branch_id,
        counted_on=body.counted_on or today(ctx.tenant.timezone),
        note=body.note,
        created_by=ctx.user.id,
        items=len(body.lines),
    )
    ctx.db.add(row)
    await ctx.db.flush()
    lines: list[dict[str, object]] = []
    total = Decimal(0)
    for line in body.lines:
        product = await _product(ctx, line.product_id)
        level = await _level(ctx.db, line.product_id, body.branch_id)
        expected = Decimal(level.quantity)
        difference = line.counted - expected
        value = Decimal(0)
        if difference:
            movement = await record(
                ctx.db,
                line.product_id,
                body.branch_id,
                "count",
                difference,
                ref_type="count",
                ref_id=row.id,
                user_id=ctx.user.id,
            )
            value = Decimal(movement.value)
        total += value
        lines.append(
            {
                "product_id": str(product.id),
                "name": product.name,
                "expected": str(expected),
                "counted": str(line.counted),
                "difference": str(difference),
                "value": costing.money(value),
            }
        )
    row.lines = lines
    await audit.record(
        ctx.db,
        "inventory.count",
        target_type="stock_count",
        target_id=row.id,
        data={"items": len(lines), "value": costing.money(total)},
    )
    await ctx.db.commit()
    return StockCountOut(
        id=row.id,
        branch_id=row.branch_id,
        counted_on=row.counted_on,
        lines=lines,
        note=row.note,
        value=costing.money(total),
    )


# ---- Suppliers ------------------------------------------------------------------------


async def _balances(ctx: Ctx, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = (
        await ctx.db.execute(
            select(SupplierEntry.supplier_id, func.sum(SupplierEntry.amount))
            .where(SupplierEntry.supplier_id.in_(ids))
            .group_by(SupplierEntry.supplier_id)
        )
    ).all()
    return {s: int(t or 0) for s, t in rows}


def _supplier_out(s: Supplier, balance: int) -> SupplierOut:
    return SupplierOut(
        id=s.id,
        name=s.name,
        phone=s.phone,
        address=s.address,
        tax_id=s.tax_id,
        note=s.note,
        active=s.active,
        balance=balance,
        version=s.version,
    )


async def suppliers(ctx: Ctx) -> list[SupplierOut]:
    ctx.require(access.VIEW)
    rows = list(await ctx.db.scalars(select(Supplier).order_by(Supplier.name)))
    balances = await _balances(ctx, [s.id for s in rows])
    return [_supplier_out(s, balances.get(s.id, 0)) for s in rows]


async def save_supplier(ctx: Ctx, body: SupplierIn, supplier_id: uuid.UUID | None = None) -> SupplierOut:
    ctx.require(access.MANAGE)
    if supplier_id:
        row = await _supplier(ctx, supplier_id, lock=True)
        for k, v in body.model_dump().items():
            setattr(row, k, v)
    else:
        row = Supplier(**body.model_dump())
        ctx.db.add(row)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "inventory.supplier_saved", target_type="supplier", target_id=row.id, data={"name": row.name}
    )
    await ctx.db.commit()
    return _supplier_out(row, (await _balances(ctx, [row.id])).get(row.id, 0))


async def pay_supplier(ctx: Ctx, supplier_id: uuid.UUID, body: SupplierPaymentIn) -> SupplierOut:
    ctx.require(access.MANAGE)
    assert ctx.tenant is not None
    row = await _supplier(ctx, supplier_id, lock=True)
    entry = SupplierEntry(
        supplier_id=row.id,
        kind="payment",
        amount=-body.amount,
        occurred_on=body.occurred_on or today(ctx.tenant.timezone),
        paid_from=body.paid_from,
        note=body.note,
        created_by=ctx.user.id,
    )
    ctx.db.add(entry)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "inventory.supplier_paid",
        target_type="supplier",
        target_id=row.id,
        data={"amount": body.amount},
    )
    await events.emit(
        ctx.db,
        "supplier.paid",
        subject_type="supplier_entry",
        subject_id=entry.id,
        data={"supplier_id": row.id, "amount": body.amount, "paid_from": body.paid_from},
    )
    await ctx.db.commit()
    return _supplier_out(row, (await _balances(ctx, [row.id])).get(row.id, 0))
