"""Payroll permissions. Salaries are sensitive: setting them is workspace-wide, not scoped."""

from app.core import permissions as perms

SELF = perms.register("payroll.self", "See own payslips", module="payroll")
VIEW = perms.register("payroll.view", "See others' finalized payslips", module="payroll", scoped=True)
MANAGE = perms.register("payroll.manage", "Set salaries, advances and payroll settings", module="payroll")
RUN = perms.register("payroll.run", "Prepare payroll runs", module="payroll")
APPROVE = perms.register(
    "payroll.approve", "Finalize payroll, mark it paid and download the transfer sheet", module="payroll"
)
