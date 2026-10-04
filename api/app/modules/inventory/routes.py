"""Inventory over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.modules.inventory import access, service
from app.modules.inventory.schemas import (
    AdjustmentIn,
    CountIn,
    CountOut,
    ItemSettingsIn,
    MovementOut,
    OpeningIn,
    PurchaseIn,
    PurchaseOut,
    StockOut,
    SupplierIn,
    SupplierOut,
    SupplierPaymentIn,
    TransferIn,
)
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/inventory", tags=["inventory"])
View = Depends(allow(access.VIEW, module=access.MODULE))
Manage = Depends(allow(access.MANAGE, module=access.MODULE))


@router.get("/stock", response_model=list[StockOut])
async def stock(
    branch_id: uuid.UUID | None = None,
    low: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    ctx: Ctx = View,
) -> list[StockOut]:
    return await service.stock(ctx, branch_id=branch_id, low_only=low, q=q)


@router.put("/items/{product_id}", response_model=StockOut)
async def item_settings(product_id: uuid.UUID, body: ItemSettingsIn, ctx: Ctx = Manage) -> StockOut:
    return await service.settings(ctx, product_id, body)


@router.get("/items/{product_id}/movements", response_model=list[MovementOut])
async def movements(product_id: uuid.UUID, ctx: Ctx = View) -> list[MovementOut]:
    return await service.movements(ctx, product_id)


@router.post("/opening", response_model=StockOut, status_code=201)
async def opening(body: OpeningIn, ctx: Ctx = Manage) -> StockOut:
    return await service.opening(ctx, body)


@router.post("/adjustments", response_model=StockOut, status_code=201)
async def adjust(body: AdjustmentIn, ctx: Ctx = Manage) -> StockOut:
    return await service.adjust(ctx, body)


@router.get("/purchases", response_model=list[PurchaseOut])
async def purchases(
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    ctx: Ctx = View,
) -> list[PurchaseOut]:
    return await service.purchases(ctx, start=start, end=end)


@router.post("/purchases", response_model=PurchaseOut, status_code=201)
async def receive(body: PurchaseIn, ctx: Ctx = Manage) -> PurchaseOut:
    return await service.receive(ctx, body)


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def purchase(purchase_id: uuid.UUID, ctx: Ctx = View) -> PurchaseOut:
    return await service.purchase(ctx, purchase_id)


@router.post("/transfers", status_code=204)
async def transfer(body: TransferIn, ctx: Ctx = Manage) -> Response:
    await service.transfer(ctx, body)
    return Response(status_code=204)


@router.post("/counts", response_model=CountOut, status_code=201)
async def count(body: CountIn, ctx: Ctx = Manage) -> CountOut:
    return await service.count(ctx, body)


@router.get("/suppliers", response_model=list[SupplierOut])
async def suppliers(ctx: Ctx = View) -> list[SupplierOut]:
    return await service.suppliers(ctx)


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
async def create_supplier(body: SupplierIn, ctx: Ctx = Manage) -> SupplierOut:
    return await service.save_supplier(ctx, body)


@router.put("/suppliers/{supplier_id}", response_model=SupplierOut)
async def save_supplier(supplier_id: uuid.UUID, body: SupplierIn, ctx: Ctx = Manage) -> SupplierOut:
    return await service.save_supplier(ctx, body, supplier_id)


@router.post("/suppliers/{supplier_id}/payments", response_model=SupplierOut)
async def pay_supplier(supplier_id: uuid.UUID, body: SupplierPaymentIn, ctx: Ctx = Manage) -> SupplierOut:
    return await service.pay_supplier(ctx, supplier_id, body)
