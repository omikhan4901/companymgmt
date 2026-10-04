"""Sales and point of sale over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.modules.platform.deps import Ctx, allow
from app.modules.sales import access, service
from app.modules.sales.schemas import (
    CloseIn,
    DrawerOut,
    OpenIn,
    ProductCategoryIn,
    ProductCategoryOut,
    ProductIn,
    ProductOut,
    ProductPatch,
    ReturnIn,
    SaleIn,
    SaleOut,
    SaleReceiptOut,
    ShopSettingsIn,
    ShopSettingsOut,
    SummaryOut,
    TaxRateIn,
    TaxRateOut,
    VoidIn,
)

router = APIRouter(prefix="/v1/sales", tags=["sales"])
Sell = Depends(allow(access.SELL, module=access.MODULE))
View = Depends(allow(access.VIEW, module=access.MODULE))
Manage = Depends(allow(access.MANAGE, module=access.MODULE))
service.register_hooks()


@router.get("/settings", response_model=ShopSettingsOut)
async def get_settings(ctx: Ctx = Sell) -> ShopSettingsOut:
    return await service.get_settings(ctx)


@router.put("/settings", response_model=ShopSettingsOut)
async def save_settings(body: ShopSettingsIn, ctx: Ctx = Manage) -> ShopSettingsOut:
    return await service.save_settings(ctx, body)


@router.get("/tax-rates", response_model=list[TaxRateOut])
async def tax_rates(ctx: Ctx = Sell) -> list[TaxRateOut]:
    return await service.tax_rates(ctx)


@router.post("/tax-rates", response_model=TaxRateOut, status_code=201)
async def create_tax_rate(body: TaxRateIn, ctx: Ctx = Manage) -> TaxRateOut:
    return await service.save_tax_rate(ctx, body)


@router.put("/tax-rates/{rate_id}", response_model=TaxRateOut)
async def save_tax_rate(rate_id: uuid.UUID, body: TaxRateIn, ctx: Ctx = Manage) -> TaxRateOut:
    return await service.save_tax_rate(ctx, body, rate_id)


@router.get("/categories", response_model=list[ProductCategoryOut])
async def categories(ctx: Ctx = Sell) -> list[ProductCategoryOut]:
    return await service.categories(ctx)


@router.post("/categories", response_model=ProductCategoryOut, status_code=201)
async def create_category(body: ProductCategoryIn, ctx: Ctx = Manage) -> ProductCategoryOut:
    return await service.save_category(ctx, body)


@router.put("/categories/{category_id}", response_model=ProductCategoryOut)
async def save_category(
    category_id: uuid.UUID, body: ProductCategoryIn, ctx: Ctx = Manage
) -> ProductCategoryOut:
    return await service.save_category(ctx, body, category_id)


@router.get("/products", response_model=list[ProductOut])
async def products(
    include_inactive: bool = False, q: Annotated[str | None, Query(max_length=100)] = None, ctx: Ctx = Sell
) -> list[ProductOut]:
    return await service.products(ctx, include_inactive=include_inactive, q=q)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductIn, ctx: Ctx = Manage) -> ProductOut:
    return await service.create_product(ctx, body)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductPatch, ctx: Ctx = Manage) -> ProductOut:
    return await service.update_product(ctx, product_id, body)


@router.get("/drawer", response_model=DrawerOut | None)
async def current_drawer(ctx: Ctx = Sell) -> DrawerOut | None:
    """Your open cash drawer, or nothing."""
    return await service.current_session(ctx)


@router.post("/drawer/open", response_model=DrawerOut, status_code=201)
async def open_drawer(body: OpenIn, ctx: Ctx = Sell) -> DrawerOut:
    return await service.open_session(ctx, body)


@router.post("/drawer/close", response_model=DrawerOut)
async def close_drawer(body: CloseIn, ctx: Ctx = Sell) -> DrawerOut:
    return await service.close_session(ctx, body)


@router.get("/drawers", response_model=list[DrawerOut])
async def drawers(ctx: Ctx = View) -> list[DrawerOut]:
    return await service.sessions(ctx)


@router.get("/summary", response_model=SummaryOut)
async def summary(
    start: Annotated[date, Query(alias="from")], end: Annotated[date, Query(alias="to")], ctx: Ctx = View
) -> SummaryOut:
    return await service.summary(ctx, start, end)


@router.get("", response_model=list[SaleOut])
async def list_sales(
    day: date | None = None, customer_id: uuid.UUID | None = None, ctx: Ctx = Sell
) -> list[SaleOut]:
    return await service.list_sales(ctx, day=day, customer_id=customer_id)


@router.post("", response_model=SaleOut, status_code=201)
async def sell(body: SaleIn, response: Response, ctx: Ctx = Sell) -> SaleOut:
    """Record a sale. Sending the same `client_id` again returns the first (200)."""
    sale, created = await service.sell(ctx, body)
    if not created:
        response.status_code = 200
    return sale


@router.get("/{sale_id}", response_model=SaleOut)
async def get_sale(sale_id: uuid.UUID, ctx: Ctx = Sell) -> SaleOut:
    return await service.get_sale(ctx, sale_id)


@router.get("/{sale_id}/receipt", response_model=SaleReceiptOut)
async def receipt(sale_id: uuid.UUID, ctx: Ctx = Sell) -> SaleReceiptOut:
    return await service.receipt(ctx, sale_id)


@router.post("/{sale_id}/returns", response_model=SaleOut, status_code=201)
async def return_items(sale_id: uuid.UUID, body: ReturnIn, ctx: Ctx = Manage) -> SaleOut:
    return await service.return_items(ctx, sale_id, body)


@router.post("/{sale_id}/void", response_model=SaleOut)
async def void(sale_id: uuid.UUID, body: VoidIn, ctx: Ctx = Manage) -> SaleOut:
    return await service.void(ctx, sale_id, body)
