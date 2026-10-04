"""Expenses over HTTP. Receipt photos are uploaded as the raw request body."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import check_if_match, read_body
from app.core.middleware import allow_upload
from app.modules.expenses import access, service
from app.modules.expenses.schemas import (
    ExpenseCategoryIn,
    ExpenseCategoryOut,
    ExpenseIn,
    ExpenseOut,
    ExpensePatch,
    ExpensesOut,
    TopUpIn,
)
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/expenses", tags=["expenses"])
allow_upload(r"/v1/expenses/[0-9a-fA-F-]{36}/receipt", service.MAX_RECEIPT + 64 * 1024)
Record = Depends(allow(access.RECORD, module=access.MODULE))
Manage = Depends(allow(access.MANAGE, module=access.MODULE))
service.register_hooks()


@router.get("", response_model=ExpensesOut)
async def list_expenses(
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    category_id: uuid.UUID | None = None,
    ctx: Ctx = Record,
) -> ExpensesOut:
    return await service.list_expenses(ctx, start=start, end=end, category_id=category_id)


@router.post("", response_model=ExpenseOut, status_code=201)
async def create(body: ExpenseIn, ctx: Ctx = Record) -> ExpenseOut:
    return await service.create(ctx, body)


@router.post("/top-ups", response_model=ExpenseOut, status_code=201)
async def top_up(body: TopUpIn, ctx: Ctx = Manage) -> ExpenseOut:
    """Money put into petty cash."""
    return await service.top_up(ctx, body)


@router.get("/categories", response_model=list[ExpenseCategoryOut])
async def categories(ctx: Ctx = Record) -> list[ExpenseCategoryOut]:
    return await service.categories(ctx)


@router.post("/categories", response_model=ExpenseCategoryOut, status_code=201)
async def create_category(body: ExpenseCategoryIn, ctx: Ctx = Manage) -> ExpenseCategoryOut:
    return await service.save_category(ctx, body)


@router.put("/categories/{category_id}", response_model=ExpenseCategoryOut)
async def save_category(
    category_id: uuid.UUID, body: ExpenseCategoryIn, ctx: Ctx = Manage
) -> ExpenseCategoryOut:
    return await service.save_category(ctx, body, category_id)


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get(expense_id: uuid.UUID, ctx: Ctx = Record) -> ExpenseOut:
    return await service.get(ctx, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update(
    expense_id: uuid.UUID, body: ExpensePatch, request: Request, ctx: Ctx = Record
) -> ExpenseOut:
    check_if_match(request, (await service.get(ctx, expense_id)).version)
    return await service.update(ctx, expense_id, body)


@router.delete("/{expense_id}", status_code=204)
async def delete(expense_id: uuid.UUID, ctx: Ctx = Manage) -> Response:
    await service.delete(ctx, expense_id)
    return Response(status_code=204)


@router.put("/{expense_id}/receipt", response_model=ExpenseOut)
async def attach(
    expense_id: uuid.UUID,
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=200)],
    ctx: Ctx = Record,
) -> ExpenseOut:
    """Body: the photo or PDF itself (up to 5 MB)."""
    data = await read_body(
        request, service.MAX_RECEIPT, message="Receipts can be up to 5 MB.", code="file_too_large"
    )
    return await service.attach(ctx, expense_id, filename, data)


@router.get("/{expense_id}/receipt")
async def receipt(expense_id: uuid.UUID, ctx: Ctx = Record) -> Response:
    data, filename, content_type = await service.receipt(ctx, expense_id)
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "'")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "content-disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            ),
            "x-content-type-options": "nosniff",
            "cache-control": "private, no-store",
        },
    )
