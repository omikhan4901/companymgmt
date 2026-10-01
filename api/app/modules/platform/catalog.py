"""Modules, business-type presets and built-in roles."""

from __future__ import annotations

from dataclasses import dataclass

from app.core import permissions as perms

# ---- Permissions owned by the platform -------------------------------------------------

WORKSPACE_MANAGE = perms.register(
    "workspace.manage", "Change workspace settings and modules", module="platform"
)
WORKSPACE_DELETE = perms.register(
    "workspace.delete", "Delete the workspace", module="platform", owner_only=True
)
BILLING_MANAGE = perms.register(
    "billing.manage", "Manage the plan and billing", module="platform", owner_only=True
)
MEMBERS_VIEW = perms.register("members.view", "See members", module="platform")
MEMBERS_INVITE = perms.register("members.invite", "Invite members and add staff", module="platform")
MEMBERS_MANAGE = perms.register(
    "members.manage",
    "Change members' roles, reset staff passwords, remove members",
    module="platform",
)
ROLES_MANAGE = perms.register("roles.manage", "Create and edit custom roles", module="platform")
BRANCHES_MANAGE = perms.register("branches.manage", "Add and edit branches", module="platform")
AUDIT_VIEW = perms.register("audit.view", "See the audit log", module="platform")


# ---- Modules ------------------------------------------------------------------------


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    # Always on for every workspace; doesn't count towards the plan's module limit.
    core: bool = False
    requires: tuple[str, ...] = ()
    available: bool = True


MODULES: dict[str, Module] = {
    m.key: m
    for m in (
        Module("people", "People", core=True),
        Module("attendance", "Attendance", requires=("people",)),
        Module("leave", "Leave", requires=("people",)),
        Module("payroll", "Payroll", requires=("people", "attendance")),
        Module("sales", "Sales & POS", available=False),
        Module("customers", "Customers & dues", available=False),
        Module("expenses", "Expenses", available=False),
        Module("inventory", "Inventory", available=False),
        Module("accounting", "Accounting", available=False),
        Module("tasks", "Tasks & projects", requires=("people",)),
    )
}

BUSINESS_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    # key: (default UI mode, modules switched on at sign-up)
    "shop": ("simple", ("attendance", "sales", "customers", "expenses")),
    "restaurant": ("simple", ("attendance", "sales", "inventory", "expenses")),
    "retail": ("standard", ("attendance", "sales", "customers", "inventory", "expenses")),
    "office": ("standard", ("attendance", "leave", "payroll", "expenses", "tasks")),
    "factory": ("advanced", ("attendance", "leave", "payroll", "inventory", "expenses", "accounting")),
    "other": ("standard", ("attendance",)),
}


def preset_modules(business_type: str) -> list[str]:
    _, wanted = BUSINESS_TYPES.get(business_type, BUSINESS_TYPES["other"])
    return [m for m in wanted if MODULES[m].available]


# ---- Built-in roles -------------------------------------------------------------------


@dataclass(frozen=True)
class BuiltinRole:
    key: str
    name: str
    description: str
    # "*" = every permission; "*-owner" = every permission except owner-only ones.
    grants: tuple[str, ...]


BUILTIN_ROLES: tuple[BuiltinRole, ...] = (
    BuiltinRole("owner", "Owner", "Full control, including billing and deleting the workspace.", ("*",)),
    BuiltinRole("admin", "Admin", "Everything except billing and deleting the workspace.", ("*-owner",)),
    BuiltinRole(
        "manager",
        "Manager",
        "Runs a team: sees and approves for their department.",
        (
            MEMBERS_VIEW,
            "people.view",
            "attendance.self",
            "attendance.view",
            "attendance.manage",
            "attendance.approve",
            "attendance.export",
            "leave.self",
            "leave.view",
            "leave.approve",
            "payroll.self",
            "payroll.view",
            "tasks.self",
            "tasks.manage",
        ),
    ),
    BuiltinRole(
        "accountant",
        "Accountant",
        "Prepares payroll; reads people, attendance and leave.",
        (
            "people.view",
            "attendance.self",
            "attendance.view",
            "attendance.export",
            "leave.self",
            "leave.view",
            "payroll.self",
            "payroll.view",
            "payroll.manage",
            "payroll.run",
            "tasks.self",
        ),
    ),
    BuiltinRole(
        "cashier",
        "Cashier",
        "Sells and clocks in. No access to other people's data.",
        ("attendance.self", "leave.self", "payroll.self", "tasks.self"),
    ),
    BuiltinRole(
        "employee",
        "Employee",
        "Clocks in, asks for leave and sees their own records.",
        ("attendance.self", "leave.self", "payroll.self", "tasks.self"),
    ),
)

DEFAULT_ROLE = "employee"


def builtin(key: str) -> BuiltinRole | None:
    return next((r for r in BUILTIN_ROLES if r.key == key), None)


def resolve(role_key: str, is_builtin: bool, custom: list[str]) -> frozenset[str]:
    """The permissions a role holds right now (built-ins follow code, so new permissions
    reach existing workspaces automatically)."""
    if not is_builtin:
        return frozenset(p for p in custom if perms.exists(p) and not perms.get(p).owner_only)
    role = builtin(role_key)
    if role is None:
        return frozenset()
    everything = perms.catalog()
    if "*" in role.grants:
        return frozenset(p.key for p in everything)
    if "*-owner" in role.grants:
        return frozenset(p.key for p in everything if not p.owner_only)
    return frozenset(p for p in role.grants if perms.exists(p))
