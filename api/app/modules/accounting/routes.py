"""The books over HTTP."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.accounting import access, service
from app.modules.accounting.schemas import (
    AccountIn,
    AccountOut,
    BalanceSheetOut,
    BooksSettingsIn,
    BooksSettingsOut,
    EntryIn,
    JournalEntryOut,
    LedgerOut,
    ProfitLossOut,
    TaxReturnOut,
    TaxTemplateIn,
    TaxTemplateOut,
    TrialBalanceOut,
)
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/accounting", tags=["accounting"])
View = Depends(allow(access.VIEW, module=access.MODULE))
Manage = Depends(allow(access.MANAGE, module=access.MODULE))
From = Annotated[date, Query(alias="from")]
To = Annotated[date, Query(alias="to")]
service.register_hooks()


@router.get("/accounts", response_model=list[AccountOut])
async def accounts(ctx: Ctx = View) -> list[AccountOut]:
    return await service.accounts(ctx)


@router.post("/accounts", response_model=AccountOut, status_code=201)
async def create_account(body: AccountIn, ctx: Ctx = Manage) -> AccountOut:
    return await service.save_account(ctx, body)


@router.put("/accounts/{account_id}", response_model=AccountOut)
async def save_account(account_id: uuid.UUID, body: AccountIn, ctx: Ctx = Manage) -> AccountOut:
    return await service.save_account(ctx, body, account_id)


@router.get("/settings", response_model=BooksSettingsOut)
async def get_settings(ctx: Ctx = View) -> BooksSettingsOut:
    return await service.get_settings(ctx)


@router.put("/settings", response_model=BooksSettingsOut)
async def save_settings(body: BooksSettingsIn, ctx: Ctx = Manage) -> BooksSettingsOut:
    return await service.save_settings(ctx, body)


@router.post("/backfill")
async def backfill(ctx: Ctx = Manage) -> dict[str, int]:
    """Post anything not in the books yet (safe to run again)."""
    return {"entries": await service.run_backfill(ctx)}


@router.get("/entries", response_model=list[JournalEntryOut])
async def entries(
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    ctx: Ctx = View,
) -> list[JournalEntryOut]:
    return await service.entries(ctx, start=start, end=end)


@router.post("/entries", response_model=JournalEntryOut, status_code=201)
async def post_entry(body: EntryIn, ctx: Ctx = Manage) -> JournalEntryOut:
    return await service.post_manual(ctx, body)


@router.post("/entries/{entry_id}/reverse", response_model=JournalEntryOut, status_code=201)
async def reverse(entry_id: uuid.UUID, ctx: Ctx = Manage) -> JournalEntryOut:
    return await service.reverse_entry(ctx, entry_id)


@router.get("/trial-balance", response_model=TrialBalanceOut)
async def trial_balance(as_of: date, ctx: Ctx = View) -> TrialBalanceOut:
    return await service.trial_balance(ctx, as_of)


@router.get("/profit-and-loss", response_model=ProfitLossOut)
async def profit_and_loss(start: From, end: To, ctx: Ctx = View) -> ProfitLossOut:
    return await service.profit_and_loss(ctx, start, end)


@router.get("/balance-sheet", response_model=BalanceSheetOut)
async def balance_sheet(as_of: date, ctx: Ctx = View) -> BalanceSheetOut:
    return await service.balance_sheet(ctx, as_of)


@router.get("/ledger/{account_id}", response_model=LedgerOut)
async def ledger(account_id: uuid.UUID, start: From, end: To, ctx: Ctx = View) -> LedgerOut:
    return await service.ledger(ctx, [account_id], start, end)


@router.get("/cash-book", response_model=LedgerOut)
async def cash_book(start: From, end: To, ctx: Ctx = View) -> LedgerOut:
    return await service.cash_book(ctx, start, end)


@router.get("/tax-returns", response_model=list[TaxTemplateOut])
async def templates(ctx: Ctx = View) -> list[TaxTemplateOut]:
    return await service.templates(ctx)


@router.post("/tax-returns", response_model=TaxTemplateOut, status_code=201)
async def create_template(body: TaxTemplateIn, ctx: Ctx = Manage) -> TaxTemplateOut:
    return await service.save_template(ctx, body)


@router.put("/tax-returns/{template_id}", response_model=TaxTemplateOut)
async def save_template(template_id: uuid.UUID, body: TaxTemplateIn, ctx: Ctx = Manage) -> TaxTemplateOut:
    return await service.save_template(ctx, body, template_id)


@router.get("/tax-returns/{template_id}/fill", response_model=TaxReturnOut)
async def fill(template_id: uuid.UUID, start: From, end: To, ctx: Ctx = View) -> TaxReturnOut:
    return await service.tax_return(ctx, template_id, start, end)
