"""Payroll capabilities (see platform/capabilities.py)."""

from __future__ import annotations

from app.modules.payroll import access, service
from app.modules.payroll.schemas import PayslipOut, RunOut
from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx

MODULE = "payroll"


@capability(
    "payroll.my_payslips",
    "Your finalized payslips, newest first.",
    output=list[PayslipOut],
    permission=access.SELF,
    module=MODULE,
    route="GET /v1/payroll/payslips",
)
async def my_payslips(ctx: Ctx, _: NoInput) -> list[PayslipOut]:
    return await service.my_payslips(ctx)


@capability(
    "payroll.runs",
    "Monthly pay runs with their totals (finalized ones, unless you prepare payroll).",
    output=list[RunOut],
    permission=access.VIEW,
    module=MODULE,
    route="GET /v1/payroll/runs",
)
async def runs(ctx: Ctx, _: NoInput) -> list[RunOut]:
    return await service.list_runs(ctx)
