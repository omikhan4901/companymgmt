"""Payroll API: settings, salaries, advances, runs and payslips.

Each route only checks who may call it and hands over to `service`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from app.modules.payroll import access, service
from app.modules.payroll.schemas import (
    ItemIn,
    ItemOut,
    LoanIn,
    LoanOut,
    PayrollSettingsIn,
    PayrollSettingsOut,
    PayslipOut,
    RunDetail,
    RunIn,
    RunOut,
    StructureIn,
    StructureOut,
)
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.routes_auth import require_recent_auth

service.register_hooks()

router = APIRouter(prefix="/v1/payroll", tags=["payroll"])
MODULE = "payroll"


# ---- Settings ---------------------------------------------------------------------------


@router.get("/settings", response_model=PayrollSettingsOut)
async def get_settings(ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> PayrollSettingsOut:
    return await service.get_settings(ctx)


@router.put("/settings", response_model=PayrollSettingsOut)
async def put_settings(
    body: PayrollSettingsIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> PayrollSettingsOut:
    return await service.put_settings(ctx, body)


# ---- Salaries ---------------------------------------------------------------------------


@router.get("/salaries", response_model=list[StructureOut])
async def salaries(ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> list[StructureOut]:
    return await service.current_structures(ctx)


@router.get("/salaries/{employee_id}", response_model=list[StructureOut])
async def salary_history(
    employee_id: uuid.UUID, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> list[StructureOut]:
    return await service.history(ctx, employee_id)


@router.post("/salaries", response_model=StructureOut, status_code=201)
async def set_salary(
    body: StructureIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))
) -> StructureOut:
    return await service.set_structure(ctx, body)


# ---- Advances and loans -----------------------------------------------------------------


@router.get("/loans", response_model=list[LoanOut])
async def loans(
    ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE)),
    employee_id: uuid.UUID | None = None,
    include_closed: bool = False,
) -> list[LoanOut]:
    return await service.list_loans(ctx, employee_id, include_closed)


@router.post("/loans", response_model=LoanOut, status_code=201)
async def add_loan(body: LoanIn, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> LoanOut:
    return await service.add_loan(ctx, body)


@router.post("/loans/{loan_id}/close", response_model=LoanOut)
async def close_loan(loan_id: uuid.UUID, ctx: Ctx = Depends(allow(access.MANAGE, module=MODULE))) -> LoanOut:
    return await service.close_loan(ctx, loan_id)


# ---- Runs -------------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunOut])
async def runs(ctx: Ctx = Depends(allow(access.VIEW, module=MODULE))) -> list[RunOut]:
    return await service.list_runs(ctx)


@router.post("/runs", response_model=RunDetail, status_code=201)
async def create_run(body: RunIn, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> RunDetail:
    return await service.create_run(ctx, body)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def run_detail(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.VIEW, module=MODULE))) -> RunDetail:
    return await service.run_detail(ctx, run_id)


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> Response:
    await service.delete_run(ctx, run_id)
    return Response(status_code=204)


@router.post("/runs/{run_id}/recompute", response_model=RunDetail)
async def recompute(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> RunDetail:
    return await service.recompute(ctx, run_id)


@router.get("/runs/{run_id}/items", response_model=list[ItemOut])
async def items(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> list[ItemOut]:
    return await service.list_items(ctx, run_id)


@router.post("/runs/{run_id}/items", response_model=ItemOut, status_code=201)
async def add_item(
    run_id: uuid.UUID, body: ItemIn, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))
) -> ItemOut:
    return await service.add_item(ctx, run_id, body)


@router.delete("/runs/{run_id}/items/{item_id}", status_code=204)
async def remove_item(
    run_id: uuid.UUID, item_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))
) -> Response:
    await service.remove_item(ctx, run_id, item_id)
    return Response(status_code=204)


@router.post("/runs/{run_id}/submit", response_model=RunDetail)
async def submit(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> RunDetail:
    return await service.submit(ctx, run_id)


@router.post("/runs/{run_id}/reopen", response_model=RunDetail)
async def reopen(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.RUN, module=MODULE))) -> RunDetail:
    return await service.reopen(ctx, run_id)


@router.post("/runs/{run_id}/finalize", response_model=RunDetail)
async def finalize(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))) -> RunDetail:
    require_recent_auth(ctx)
    return await service.finalize(ctx, run_id)


@router.post("/runs/{run_id}/paid", response_model=RunDetail)
async def mark_paid(run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))) -> RunDetail:
    return await service.mark_paid(ctx, run_id)


@router.get("/runs/{run_id}/transfers.csv")
async def transfer_sheet(
    run_id: uuid.UUID, ctx: Ctx = Depends(allow(access.APPROVE, module=MODULE))
) -> StreamingResponse:
    require_recent_auth(ctx)
    body, filename = await service.transfer_sheet(ctx, run_id)
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- Payslips ---------------------------------------------------------------------------


@router.get("/payslips", response_model=list[PayslipOut])
async def my_payslips(ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> list[PayslipOut]:
    return await service.my_payslips(ctx)


@router.get("/payslips/{payslip_id}", response_model=PayslipOut)
async def payslip(payslip_id: uuid.UUID, ctx: Ctx = Depends(allow(access.SELF, module=MODULE))) -> PayslipOut:
    return await service.payslip(ctx, payslip_id)
