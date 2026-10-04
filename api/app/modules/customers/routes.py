"""Customers and dues over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.http import check_if_match
from app.modules.customers import access, service
from app.modules.customers.schemas import (
    AdjustmentIn,
    CustomerIn,
    CustomerOut,
    CustomerPatch,
    PaymentIn,
    StatementOut,
)
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/customers", tags=["customers"])
View = Depends(allow(access.VIEW, module=access.MODULE))
Manage = Depends(allow(access.MANAGE, module=access.MODULE))


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    q: Annotated[str | None, Query(max_length=100)] = None, owing: bool = False, ctx: Ctx = View
) -> list[CustomerOut]:
    return await service.list_customers(ctx, q=q, owing=owing)


@router.post("", response_model=CustomerOut, status_code=201)
async def create(body: CustomerIn, ctx: Ctx = Manage) -> CustomerOut:
    return await service.create(ctx, body)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get(customer_id: uuid.UUID, ctx: Ctx = View) -> CustomerOut:
    return await service.get(ctx, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update(
    customer_id: uuid.UUID, body: CustomerPatch, request: Request, ctx: Ctx = Manage
) -> CustomerOut:
    check_if_match(request, (await service.get(ctx, customer_id)).version)
    return await service.update(ctx, customer_id, body)


@router.post("/{customer_id}/payments", response_model=CustomerOut)
async def pay(customer_id: uuid.UUID, body: PaymentIn, ctx: Ctx = Manage) -> CustomerOut:
    return await service.pay(ctx, customer_id, body)


@router.post("/{customer_id}/adjustments", response_model=CustomerOut)
async def adjust(customer_id: uuid.UUID, body: AdjustmentIn, ctx: Ctx = Manage) -> CustomerOut:
    return await service.adjust(ctx, customer_id, body)


@router.get("/{customer_id}/statement", response_model=StatementOut)
async def statement(
    customer_id: uuid.UUID,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    ctx: Ctx = View,
) -> StatementOut:
    return await service.statement(ctx, customer_id, start, end)
