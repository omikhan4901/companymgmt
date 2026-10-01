"""Workspace settings, modules, members, staff accounts, invites, roles, branches and the
audit log."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator
from sqlalchemy import Select, func, literal, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, context, ratelimit
from app.core import permissions as perms
from app.core.db import get_db, set_tenant
from app.core.errors import Conflict, Forbidden, Invalid, NotFound, PaymentRequired, Unauthorized
from app.core.http import check_if_match, decode_cursor, encode_cursor, set_etag
from app.core.schema import In, Out, Page, ShortName
from app.core.security import passwords
from app.core.security.tokens import decode_access_token, hash_secret, new_secret
from app.modules.platform import catalog, emails, hooks, workspaces
from app.modules.platform.catalog import (
    AUDIT_VIEW,
    BRANCHES_MANAGE,
    MEMBERS_INVITE,
    MEMBERS_MANAGE,
    MEMBERS_VIEW,
    ROLES_MANAGE,
    WORKSPACE_DELETE,
    WORKSPACE_MANAGE,
)
from app.modules.platform.deps import DELETION_GRACE, Ctx, allow, owner_of_deleted_workspace, public
from app.modules.platform.models import (
    AuthSession,
    Branch,
    Invite,
    Membership,
    Role,
    Subscription,
    Tenant,
    User,
)
from app.modules.platform.routes_auth import (
    TokenOut,
    _set_refresh_cookie,
    commit_and_dispatch,
    require_recent_auth,
)
from app.modules.platform.tokens import log_event, now, revoke_user_sessions, start_session

router = APIRouter(prefix="/v1", tags=["workspace"])

INVITE_DAYS = 7
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


# ---- Workspace settings and modules ----------------------------------------------------


class WorkspaceOut(Out):
    id: uuid.UUID
    name: str
    slug: str
    business_type: str
    ui_mode: str
    country: str | None
    currency: str
    timezone: str
    locale: str
    week_start: int
    fiscal_year_start_month: int
    require_admin_mfa: bool
    created_at: datetime


class WorkspaceIn(In):
    name: ShortName | None = None
    ui_mode: Literal["simple", "standard", "advanced"] | None = None
    country: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")] | None = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    timezone: Annotated[str, StringConstraints(max_length=64)] | None = None
    locale: Literal["en", "bn"] | None = None
    week_start: int | None = Field(default=None, ge=0, le=6)
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    require_admin_mfa: bool | None = None


class ModulesIn(In):
    modules: list[Annotated[str, StringConstraints(max_length=30)]] = Field(max_length=30)


@router.get("/workspace", response_model=WorkspaceOut)
async def get_workspace(ctx: Ctx = Depends(allow(None))) -> WorkspaceOut:
    return WorkspaceOut.model_validate(ctx.tenant)


@router.patch("/workspace", response_model=WorkspaceOut)
async def update_workspace(body: WorkspaceIn, ctx: Ctx = Depends(allow(WORKSPACE_MANAGE))) -> WorkspaceOut:
    tenant = ctx.tenant
    assert tenant is not None
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "timezone" in changes:
        workspaces.valid_timezone(changes["timezone"])
    if changes.get("require_admin_mfa") and ctx.user.totp_enabled_at is None:
        # Otherwise the person turning it on would lock themselves out.
        raise Invalid(
            "Turn on two-step verification for your own account first.",
            code="mfa_required_first",
            errors=[
                {"field": "require_admin_mfa", "message": "Turn on two-step verification for yourself first."}
            ],
        )
    before = {k: getattr(tenant, k) for k in changes}
    await ctx.db.execute(update(Tenant).where(Tenant.id == tenant.id).values(**changes))
    await audit.record(
        ctx.db,
        "workspace.updated",
        target_type="workspace",
        target_id=tenant.id,
        data={"before": before, "after": changes},
    )
    await ctx.db.commit()
    await ctx.db.refresh(tenant)
    return WorkspaceOut.model_validate(tenant)


@router.put("/workspace/modules", response_model=list[str])
async def set_modules(body: ModulesIn, ctx: Ctx = Depends(allow(WORKSPACE_MANAGE))) -> list[str]:
    wanted: list[str] = []
    for key in body.modules:
        module = catalog.MODULES.get(key)
        if module is None or not module.available:
            raise Invalid(errors=[{"field": "modules", "message": f"Unknown or unavailable module: {key}"}])
        if not module.core and key not in wanted:
            wanted.append(key)
    for key in wanted:
        missing = [
            r for r in catalog.MODULES[key].requires if not catalog.MODULES[r].core and r not in wanted
        ]
        if missing:
            raise Invalid(
                errors=[
                    {
                        "field": "modules",
                        "message": f"{catalog.MODULES[key].name} needs {', '.join(missing)}.",
                    }
                ]
            )
    assert ctx.entitlements is not None
    limit = ctx.entitlements.plan.max_modules
    if limit is not None and len(wanted) > limit:
        raise PaymentRequired(
            f"Your plan includes {limit} modules.", code="module_limit", extra={"limit": limit}
        )
    sub = await ctx.db.scalar(select(Subscription).with_for_update())
    assert sub is not None
    before = list(sub.modules)
    sub.modules = wanted
    assert ctx.tenant is not None
    await hooks.enable_modules(ctx.db, ctx.tenant, [m for m in wanted if m not in before])
    await audit.record(
        ctx.db,
        "workspace.modules_changed",
        target_type="workspace",
        target_id=ctx.tenant_id,
        data={"before": before, "after": wanted},
    )
    await ctx.db.commit()
    return wanted


# ---- Deleting and restoring the workspace ---------------------------------------------


class DeleteWorkspaceIn(In):
    # The workspace name, typed again, so nobody deletes the wrong one by accident.
    confirm_name: Annotated[str, StringConstraints(max_length=200)]


class DeletionOut(BaseModel):
    status: str
    purge_after: datetime | None


@router.post("/workspace/delete", response_model=DeletionOut)
async def delete_workspace(
    body: DeleteWorkspaceIn, ctx: Ctx = Depends(allow(WORKSPACE_DELETE))
) -> DeletionOut:
    require_recent_auth(ctx)
    tenant = ctx.tenant
    assert tenant is not None
    if body.confirm_name.strip().casefold() != tenant.name.strip().casefold():
        raise Invalid(errors=[{"field": "confirm_name", "message": "Type the workspace name exactly."}])
    requested = now()
    await ctx.db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .values(status="deleting", deletion_requested_at=requested, deletion_contact=ctx.user.email)
    )
    purge_after = requested + DELETION_GRACE
    await audit.record(
        ctx.db,
        "workspace.deletion_requested",
        target_type="workspace",
        target_id=tenant.id,
        data={"name": tenant.name, "purge_after": purge_after},
    )
    if ctx.user.email:
        emails.send(
            ctx.db,
            "deletion_scheduled",
            ctx.user.email,
            ctx.user.locale or tenant.locale,
            name=ctx.user.name,
            workspace=tenant.name,
            date=purge_after.date().isoformat(),
            link=emails.link("/login"),
        )
    await commit_and_dispatch(ctx.db)
    return DeletionOut(status="deleting", purge_after=purge_after)


@router.post("/workspace/restore", response_model=DeletionOut)
async def restore_workspace(ctx: Ctx = Depends(owner_of_deleted_workspace())) -> DeletionOut:
    require_recent_auth(ctx)
    assert ctx.tenant is not None
    await ctx.db.execute(
        update(Tenant)
        .where(Tenant.id == ctx.tenant.id)
        .values(status="active", deletion_requested_at=None, deletion_contact=None)
    )
    await audit.record(
        ctx.db,
        "workspace.restored",
        target_type="workspace",
        target_id=ctx.tenant.id,
        data={"name": ctx.tenant.name},
    )
    await ctx.db.commit()
    return DeletionOut(status="active", purge_after=None)


# ---- Roles ------------------------------------------------------------------------------


class RoleOut(Out):
    id: uuid.UUID
    key: str
    name: str
    description: str | None
    is_builtin: bool
    permissions: list[str]
    members: int


class RoleIn(In):
    name: ShortName
    description: Annotated[str, StringConstraints(max_length=300)] | None = None
    permissions: list[Annotated[str, StringConstraints(max_length=60)]] = Field(max_length=200)


class RolePatch(In):
    name: ShortName | None = None
    description: Annotated[str, StringConstraints(max_length=300)] | None = None
    permissions: list[Annotated[str, StringConstraints(max_length=60)]] | None = Field(
        default=None, max_length=200
    )


class PermissionOut(Out):
    key: str
    module: str
    label: str
    scoped: bool
    owner_only: bool


def _role_perms(role: Role) -> frozenset[str]:
    return catalog.resolve(role.key, role.is_builtin, list(role.permissions or []))


def _check_grantable(ctx: Ctx, granted: frozenset[str] | set[str]) -> None:
    """Nobody can hand out permissions they don't hold themselves."""
    if ctx.is_owner:
        return
    extra = set(granted) - set(ctx.permissions)
    if extra:
        raise Forbidden("You can't give permissions you don't have yourself.", code="escalation")


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(ctx: Ctx = Depends(allow(MEMBERS_VIEW))) -> list[PermissionOut]:
    return [PermissionOut(**vars(p)) for p in perms.catalog()]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(ctx: Ctx = Depends(allow(MEMBERS_VIEW))) -> list[RoleOut]:
    rows = await ctx.db.execute(
        select(Membership.role_id, func.count())
        .where(Membership.status == "active")
        .group_by(Membership.role_id)
    )
    counts: dict[uuid.UUID, int] = {row[0]: row[1] for row in rows}
    roles = (await ctx.db.scalars(select(Role).order_by(Role.is_builtin.desc(), Role.created_at))).all()
    return [
        RoleOut(
            id=r.id,
            key=r.key,
            name=r.name,
            description=r.description,
            is_builtin=r.is_builtin,
            permissions=sorted(_role_perms(r)),
            members=counts.get(r.id, 0),
        )
        for r in roles
    ]


def _validate_permissions(keys: list[str]) -> list[str]:
    clean: list[str] = []
    for key in keys:
        if not perms.exists(key):
            raise Invalid(errors=[{"field": "permissions", "message": f"Unknown permission: {key}"}])
        if perms.get(key).owner_only:
            raise Invalid(errors=[{"field": "permissions", "message": f"Only owners can have {key}."}])
        if key not in clean:
            clean.append(key)
    return clean


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(body: RoleIn, ctx: Ctx = Depends(allow(ROLES_MANAGE))) -> RoleOut:
    assert ctx.entitlements is not None
    if not ctx.entitlements.feature("custom_roles"):
        raise PaymentRequired("Custom roles are on the Growth plan and above.", code="feature_custom_roles")
    keys = _validate_permissions(body.permissions)
    _check_grantable(ctx, set(keys))
    role = Role(
        key=f"custom-{secrets.token_hex(4)}",
        name=body.name,
        description=body.description,
        is_builtin=False,
        permissions=keys,
    )
    ctx.db.add(role)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "role.created",
        target_type="role",
        target_id=role.id,
        data={"name": body.name, "permissions": keys},
    )
    await ctx.db.commit()
    return RoleOut(
        id=role.id,
        key=role.key,
        name=role.name,
        description=role.description,
        is_builtin=False,
        permissions=sorted(keys),
        members=0,
    )


async def _custom_role(ctx: Ctx, role_id: uuid.UUID) -> Role:
    role = await ctx.db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if role is None:
        raise NotFound()
    if role.is_builtin:
        raise Forbidden("Built-in roles can't be changed. Create a custom role instead.", code="builtin_role")
    return role


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: uuid.UUID, body: RolePatch, ctx: Ctx = Depends(allow(ROLES_MANAGE))
) -> RoleOut:
    role = await _custom_role(ctx, role_id)
    before = {"name": role.name, "permissions": list(role.permissions)}
    if body.permissions is not None:
        keys = _validate_permissions(body.permissions)
        _check_grantable(ctx, set(keys) | set(role.permissions))
        role.permissions = keys
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    await audit.record(
        ctx.db,
        "role.updated",
        target_type="role",
        target_id=role.id,
        data={"before": before, "after": {"name": role.name, "permissions": role.permissions}},
    )
    await ctx.db.commit()
    count = await ctx.db.scalar(
        select(func.count()).select_from(Membership).where(Membership.role_id == role.id)
    )
    return RoleOut(
        id=role.id,
        key=role.key,
        name=role.name,
        description=role.description,
        is_builtin=False,
        permissions=sorted(role.permissions),
        members=count or 0,
    )


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(role_id: uuid.UUID, ctx: Ctx = Depends(allow(ROLES_MANAGE))) -> None:
    role = await _custom_role(ctx, role_id)
    in_use = await ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.role_id == role.id, Membership.status != "removed")
    )
    pending = await ctx.db.scalar(
        select(func.count())
        .select_from(Invite)
        .where(Invite.role_id == role.id, Invite.accepted_at.is_(None), Invite.revoked_at.is_(None))
    )
    if in_use or pending:
        raise Conflict("Move members to another role first.", code="role_in_use")
    await audit.record(
        ctx.db, "role.deleted", target_type="role", target_id=role.id, data={"name": role.name}
    )
    await ctx.db.delete(role)
    await ctx.db.commit()


# ---- Members ----------------------------------------------------------------------------


class MemberOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str | None
    username: str | None
    role_id: uuid.UUID
    role: str
    role_key: str
    status: str
    scope_department_id: uuid.UUID | None
    mfa_enabled: bool
    staff_account: bool
    joined_at: datetime
    version: int


class MemberPatch(In):
    role_id: uuid.UUID | None = None
    scope_department_id: uuid.UUID | None = None
    clear_scope: bool = False
    status: Literal["active", "disabled"] | None = None


class StaffIn(In):
    name: ShortName
    username: Annotated[str, StringConstraints(min_length=3, max_length=40)]
    password: Annotated[str, StringConstraints(max_length=passwords.MAX_LENGTH)] | None = None
    role_id: uuid.UUID
    scope_department_id: uuid.UUID | None = None

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        value = value.strip().lower()
        if not USERNAME.match(value):
            raise ValueError("Use 3-40 letters, numbers, dots, dashes or underscores.")
        return value


class StaffOut(Out):
    member: MemberOut
    temporary_password: str | None
    workspace_code: str


class TempPasswordOut(Out):
    temporary_password: str


def _member_out(m: Membership, u: User, r: Role) -> MemberOut:
    return MemberOut(
        id=m.id,
        user_id=u.id,
        name=u.name,
        email=u.email,
        username=u.username,
        role_id=r.id,
        role=r.name,
        role_key=r.key,
        status=m.status,
        scope_department_id=m.scope_department_id,
        mfa_enabled=u.totp_enabled_at is not None,
        staff_account=u.managed_tenant_id is not None,
        joined_at=m.created_at,
        version=m.version,
    )


def _member_query() -> Select[Membership, User, Role]:
    return (
        select(Membership, User, Role)
        .join(User, User.id == Membership.user_id)
        .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
    )


@router.get("/members", response_model=Page[MemberOut])
async def list_members(
    ctx: Ctx = Depends(allow(MEMBERS_VIEW)),
    status: Literal["active", "disabled", "removed", "all"] = "active",
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> Page[MemberOut]:
    query = _member_query()
    if status != "all":
        query = query.where(Membership.status == status)
    after = decode_cursor(cursor)
    if after:
        query = query.where(
            tuple_(func.lower(User.name), Membership.id)
            > tuple_(literal(str(after["n"])), literal(uuid.UUID(str(after["id"]))))
        )
    rows = (await ctx.db.execute(query.order_by(func.lower(User.name), Membership.id).limit(limit + 1))).all()
    items = [_member_out(m, u, r) for m, u, r in rows[:limit]]
    next_cursor = (
        encode_cursor({"n": items[-1].name.lower(), "id": items[-1].id}) if len(rows) > limit else None
    )
    return Page(items=items, next_cursor=next_cursor)


async def _load_member(ctx: Ctx, member_id: uuid.UUID) -> tuple[Membership, User, Role]:
    row = (
        await ctx.db.execute(_member_query().where(Membership.id == member_id).with_for_update(of=Membership))
    ).first()
    if row is None:
        raise NotFound()
    return row[0], row[1], row[2]


async def _active_owner_count(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Membership)
        .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
        .where(Membership.status == "active", Role.key == "owner", Role.is_builtin.is_(True))
    )
    return count or 0


def _is_owner_role(role: Role) -> bool:
    return role.is_builtin and role.key == "owner"


async def _role_for_assignment(ctx: Ctx, role_id: uuid.UUID) -> Role:
    role = await ctx.db.scalar(select(Role).where(Role.id == role_id))
    if role is None:
        raise Invalid(errors=[{"field": "role_id", "message": "Unknown role."}])
    if _is_owner_role(role) and not ctx.is_owner:
        raise Forbidden("Only owners can make someone an owner.", code="escalation")
    _check_grantable(ctx, _role_perms(role))
    return role


async def _check_scope(ctx: Ctx, department_id: uuid.UUID | None) -> None:
    if department_id is not None and not await hooks.valid_department(ctx.db, department_id):
        raise Invalid(errors=[{"field": "scope_department_id", "message": "Unknown department."}])


@router.patch("/members/{member_id}", response_model=MemberOut)
async def update_member(
    member_id: uuid.UUID,
    body: MemberPatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(MEMBERS_MANAGE)),
) -> MemberOut:
    member, user, role = await _load_member(ctx, member_id)
    check_if_match(request, member.version)
    if ctx.membership is not None and member.id == ctx.membership.id:
        raise Forbidden("You can't change your own membership. Ask another admin.", code="self_edit")
    if member.status == "removed":
        raise Conflict("This person was removed. Invite them again instead.", code="member_removed")
    if _is_owner_role(role) and not ctx.is_owner:
        raise Forbidden("Only owners can change an owner.", code="owner_protected")
    before = {"role": role.key, "status": member.status, "scope": member.scope_department_id}
    new_role = role
    if body.role_id is not None and body.role_id != role.id:
        new_role = await _role_for_assignment(ctx, body.role_id)
    losing_owner = _is_owner_role(role) and (not _is_owner_role(new_role) or body.status == "disabled")
    if losing_owner and await _active_owner_count(ctx.db) <= 1:
        raise Conflict("A workspace needs at least one owner.", code="last_owner")
    member.role_id = new_role.id
    if body.clear_scope:
        member.scope_department_id = None
    elif body.scope_department_id is not None:
        await _check_scope(ctx, body.scope_department_id)
        member.scope_department_id = body.scope_department_id
    if body.status is not None:
        member.status = body.status
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "member.updated",
        target_type="member",
        target_id=member.id,
        data={
            "user": user.name,
            "before": before,
            "after": {"role": new_role.key, "status": member.status, "scope": member.scope_department_id},
        },
    )
    await ctx.db.commit()
    set_etag(response, member.version)
    return _member_out(member, user, new_role)


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(member_id: uuid.UUID, ctx: Ctx = Depends(allow(MEMBERS_MANAGE))) -> None:
    member, user, role = await _load_member(ctx, member_id)
    if ctx.membership and member.id == ctx.membership.id:
        raise Forbidden(
            "You can't remove yourself here. Leave the workspace from your account.", code="self_edit"
        )
    if _is_owner_role(role):
        if not ctx.is_owner:
            raise Forbidden("Only owners can remove an owner.", code="owner_protected")
        if member.status == "active" and await _active_owner_count(ctx.db) <= 1:
            raise Conflict("A workspace needs at least one owner.", code="last_owner")
    if member.status == "removed":
        return
    member.status = "removed"
    await ctx.db.flush()
    await hooks.run(hooks.member_removed, ctx.db, member, user)
    await revoke_user_sessions(ctx.db, user.id, "member_removed", tenant_id=ctx.tenant_id)
    if user.managed_tenant_id == ctx.tenant_id:
        user.disabled_at = now()
    await audit.record(
        ctx.db,
        "member.removed",
        target_type="member",
        target_id=member.id,
        data={"user": user.name, "role": role.key},
    )
    await ctx.db.commit()


def _temp_password() -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


@router.post("/members/staff", response_model=StaffOut, status_code=201)
async def add_staff(body: StaffIn, ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> StaffOut:
    role = await _role_for_assignment(ctx, body.role_id)
    await _check_scope(ctx, body.scope_department_id)
    taken = await ctx.db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.managed_tenant_id == ctx.tenant_id, func.lower(User.username) == body.username)
    )
    if taken:
        raise Invalid(errors=[{"field": "username", "message": "This username is taken in your workspace."}])
    temporary = body.password is None
    password = body.password or _temp_password()
    if not temporary:
        issues = passwords.problems(password, context=(body.name, body.username))
        if issues:
            raise Invalid(errors=[{"field": "password", "message": m} for m in issues])
    user = User(
        name=body.name,
        username=body.username,
        managed_tenant_id=ctx.tenant_id,
        password_hash=passwords.hash_password(password),
        password_changed_at=now(),
        must_change_password=True,
        locale=ctx.tenant.locale if ctx.tenant else "en",
    )
    ctx.db.add(user)
    await ctx.db.flush()
    member = Membership(user_id=user.id, role_id=role.id, scope_department_id=body.scope_department_id)
    ctx.db.add(member)
    await ctx.db.flush()
    await hooks.run(hooks.member_joined, ctx.db, member, user)
    await audit.record(
        ctx.db,
        "member.staff_added",
        target_type="member",
        target_id=member.id,
        data={"name": body.name, "username": body.username, "role": role.key},
    )
    await ctx.db.commit()
    assert ctx.tenant is not None
    return StaffOut(
        member=_member_out(member, user, role),
        temporary_password=password if temporary else None,
        workspace_code=ctx.tenant.slug,
    )


@router.post("/members/{member_id}/reset-password", response_model=TempPasswordOut)
async def reset_staff_password(
    member_id: uuid.UUID, ctx: Ctx = Depends(allow(MEMBERS_MANAGE))
) -> TempPasswordOut:
    member, user, role = await _load_member(ctx, member_id)
    if user.managed_tenant_id != ctx.tenant_id:
        raise Invalid(
            "Only staff accounts can be reset here. Others use “Forgot password”.", code="not_staff"
        )
    _check_grantable(ctx, _role_perms(role))
    password = _temp_password()
    user.password_hash = passwords.hash_password(password)
    user.password_changed_at = now()
    user.must_change_password = True
    await revoke_user_sessions(ctx.db, user.id, "password_reset_by_admin")
    log_event(ctx.db, user.id, "password.reset_by_admin", by=ctx.user.id)
    await audit.record(
        ctx.db, "member.password_reset", target_type="member", target_id=member.id, data={"user": user.name}
    )
    await ctx.db.commit()
    return TempPasswordOut(temporary_password=password)


# ---- Invites ----------------------------------------------------------------------------


class InviteIn(In):
    email: EmailStr
    name: ShortName | None = None
    role_id: uuid.UUID
    scope_department_id: uuid.UUID | None = None


class InviteOut(Out):
    id: uuid.UUID
    email: str
    name: str | None
    role_id: uuid.UUID
    created_at: datetime
    expires_at: datetime


class InviteLookupOut(Out):
    workspace: str
    email: str
    name: str | None
    account_exists: bool


class AcceptIn(In):
    token: Annotated[str, StringConstraints(max_length=200)]
    name: ShortName | None = None
    password: Annotated[str, StringConstraints(max_length=passwords.MAX_LENGTH)] | None = None


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(ctx: Ctx = Depends(allow(MEMBERS_VIEW))) -> list[InviteOut]:
    rows = await ctx.db.scalars(
        select(Invite)
        .where(Invite.accepted_at.is_(None), Invite.revoked_at.is_(None), Invite.expires_at > now())
        .order_by(Invite.created_at.desc())
    )
    return [InviteOut.model_validate(i) for i in rows]


@router.post("/invites", response_model=InviteOut, status_code=201)
async def create_invite(body: InviteIn, ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> InviteOut:
    if ctx.user.email and not ctx.user.email_verified_at:
        raise Forbidden("Confirm your email address before inviting people.", code="email_unverified")
    await ratelimit.enforce(ratelimit.INVITE_TENANT, str(ctx.tenant_id))
    role = await _role_for_assignment(ctx, body.role_id)
    await _check_scope(ctx, body.scope_department_id)
    email = body.email.lower()
    already = await ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(func.lower(User.email) == email, Membership.status == "active")
    )
    if already:
        raise Conflict("This person is already a member.", code="already_member")
    await ctx.db.execute(
        update(Invite)
        .where(func.lower(Invite.email) == email, Invite.accepted_at.is_(None), Invite.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    secret = new_secret()
    token = f"{ctx.tenant_id}.{secret}"
    invite = Invite(
        email=email,
        name=body.name,
        role_id=role.id,
        scope_department_id=body.scope_department_id,
        token_hash=hash_secret(secret),
        invited_by=ctx.user.id,
        expires_at=now() + timedelta(days=INVITE_DAYS),
    )
    ctx.db.add(invite)
    await ctx.db.flush()
    assert ctx.tenant is not None
    emails.send(
        ctx.db,
        "invite",
        email,
        ctx.tenant.locale,
        name=body.name or email,
        inviter=ctx.user.name,
        workspace=ctx.tenant.name,
        link=emails.link(f"/invite?token={token}"),
    )
    await audit.record(
        ctx.db,
        "invite.created",
        target_type="invite",
        target_id=invite.id,
        data={"email": email, "role": role.key},
    )
    await commit_and_dispatch(ctx.db)
    return InviteOut.model_validate(invite)


@router.delete("/invites/{invite_id}", status_code=204)
async def revoke_invite(invite_id: uuid.UUID, ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> None:
    invite = await ctx.db.scalar(select(Invite).where(Invite.id == invite_id).with_for_update())
    if invite is None:
        raise NotFound()
    if invite.accepted_at is None and invite.revoked_at is None:
        invite.revoked_at = now()
        await audit.record(
            ctx.db, "invite.revoked", target_type="invite", target_id=invite.id, data={"email": invite.email}
        )
        await ctx.db.commit()


async def _open_invite(db: AsyncSession, token: str) -> Invite:
    tenant_part, _, secret = token.partition(".")
    try:
        tenant_id = uuid.UUID(tenant_part)
    except ValueError as exc:
        raise Invalid("This invitation link isn't valid.", code="invite_invalid") from exc
    await set_tenant(db, tenant_id)
    invite = await db.scalar(select(Invite).where(Invite.token_hash == hash_secret(secret)).with_for_update())
    if invite is None or invite.revoked_at is not None:
        raise Invalid("This invitation isn't valid any more. Ask for a new one.", code="invite_invalid")
    if invite.accepted_at is not None:
        raise Invalid("This invitation was already used.", code="invite_used")
    if invite.expires_at <= now():
        raise Invalid("This invitation expired. Ask for a new one.", code="invite_expired")
    return invite


@router.get("/invites/lookup", response_model=InviteLookupOut)
async def lookup_invite(
    token: Annotated[str, Query(max_length=200)],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> InviteLookupOut:
    await ratelimit.enforce(ratelimit.RESET_IP, context.current().ip or "unknown")
    invite = await _open_invite(db, token)
    tenant = await db.get(Tenant, invite.tenant_id)
    assert tenant is not None
    exists = await db.scalar(
        select(func.count()).select_from(User).where(func.lower(User.email) == invite.email)
    )
    return InviteLookupOut(
        workspace=tenant.name, email=invite.email, name=invite.name, account_exists=bool(exists)
    )


@router.post("/invites/accept", response_model=TokenOut)
async def accept_invite(
    body: AcceptIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> TokenOut:
    """Accept as the signed-in user (bearer token), or create an account for the invited email."""
    await ratelimit.enforce(ratelimit.RESET_IP, context.current().ip or "unknown")
    invite = await _open_invite(db, body.token)
    tenant_id = invite.tenant_id
    user = await db.scalar(
        select(User).where(func.lower(User.email) == invite.email, User.managed_tenant_id.is_(None))
    )
    header = request.headers.get("authorization", "")
    claims = decode_access_token(header[7:]) if header.lower().startswith("bearer ") else None
    if user is not None:
        session = await db.get(AuthSession, claims.session_id) if claims else None
        if claims is None or session is None or session.revoked_at is not None or claims.user_id != user.id:
            raise Unauthorized("Sign in as the invited email address to accept.", code="sign_in_to_accept")
    else:
        if not body.password or not body.name:
            raise Invalid(errors=[{"field": "password", "message": "Choose a name and password."}])
        issues = passwords.problems(body.password, context=(body.name, invite.email.split("@")[0]))
        if issues:
            raise Invalid(errors=[{"field": "password", "message": m} for m in issues])
        user = User(
            email=invite.email,
            name=body.name,
            email_verified_at=now(),
            password_hash=passwords.hash_password(body.password),
            password_changed_at=now(),
        )
        db.add(user)
        await db.flush()
    existing = await db.scalar(select(Membership).where(Membership.user_id == user.id).with_for_update())
    if existing is not None and existing.status == "active":
        raise Conflict("You're already a member of this workspace.", code="already_member")
    if existing is not None:
        existing.status = "active"
        existing.role_id = invite.role_id
        existing.scope_department_id = invite.scope_department_id
        membership = existing
    else:
        membership = Membership(
            user_id=user.id, role_id=invite.role_id, scope_department_id=invite.scope_department_id
        )
        db.add(membership)
    await db.flush()
    await hooks.run(hooks.member_joined, db, membership, user)
    invite.accepted_at = now()
    await audit.record(
        db,
        "invite.accepted",
        target_type="member",
        target_id=membership.id,
        data={"email": invite.email},
        actor_user_id=user.id,
    )
    issued = await start_session(db, user, tenant_id, mfa=False)
    await db.commit()
    _set_refresh_cookie(response, issued.refresh_token)
    return TokenOut(access_token=issued.access_token, expires_at=issued.access_expires_at)


# ---- Branches ---------------------------------------------------------------------------


class BranchOut(Out):
    id: uuid.UUID
    name: str
    timezone: str
    address: str | None
    is_active: bool
    latitude: float | None
    longitude: float | None
    geofence_m: int
    version: int


Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Radius = Annotated[int, Field(ge=25, le=5000)]


class BranchIn(In):
    name: ShortName
    timezone: Annotated[str, StringConstraints(max_length=64)] | None = None
    address: Annotated[str, StringConstraints(max_length=500)] | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    geofence_m: Radius = 150


class BranchPatch(In):
    name: ShortName | None = None
    timezone: Annotated[str, StringConstraints(max_length=64)] | None = None
    address: Annotated[str, StringConstraints(max_length=500)] | None = None
    is_active: bool | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    geofence_m: Radius | None = None
    # Forget the branch's location (location checks then skip it).
    clear_location: bool = False


def _check_location_pair(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise Invalid(errors=[{"field": "longitude", "message": "Give both latitude and longitude."}])


@router.get("/branches", response_model=list[BranchOut])
async def list_branches(ctx: Ctx = Depends(allow(None))) -> list[BranchOut]:
    rows = await ctx.db.scalars(select(Branch).order_by(Branch.is_active.desc(), func.lower(Branch.name)))
    return [BranchOut.model_validate(b) for b in rows]


@router.post("/branches", response_model=BranchOut, status_code=201)
async def create_branch(body: BranchIn, ctx: Ctx = Depends(allow(BRANCHES_MANAGE))) -> BranchOut:
    assert ctx.entitlements is not None
    assert ctx.tenant is not None
    limit = ctx.entitlements.plan.max_branches
    active = await ctx.db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True)))
    if limit is not None and (active or 0) >= limit:
        raise PaymentRequired(
            f"Your plan includes {limit} branch{'es' if limit != 1 else ''}.",
            code="branch_limit",
            extra={"limit": limit},
        )
    await _unique_branch_name(ctx, body.name)
    _check_location_pair(body.latitude, body.longitude)
    branch = Branch(
        name=body.name,
        address=body.address,
        timezone=workspaces.valid_timezone(body.timezone) if body.timezone else ctx.tenant.timezone,
        latitude=_coord(body.latitude),
        longitude=_coord(body.longitude),
        geofence_m=body.geofence_m,
    )
    ctx.db.add(branch)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "branch.created", target_type="branch", target_id=branch.id, data={"name": body.name}
    )
    await ctx.db.commit()
    return BranchOut.model_validate(branch)


def _coord(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 6)))


async def _unique_branch_name(ctx: Ctx, name: str, exclude: uuid.UUID | None = None) -> None:
    query = select(func.count()).select_from(Branch).where(func.lower(Branch.name) == name.lower())
    if exclude:
        query = query.where(Branch.id != exclude)
    if await ctx.db.scalar(query):
        raise Invalid(errors=[{"field": "name", "message": "A branch with this name already exists."}])


@router.patch("/branches/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID,
    body: BranchPatch,
    request: Request,
    response: Response,
    ctx: Ctx = Depends(allow(BRANCHES_MANAGE)),
) -> BranchOut:
    branch = await ctx.db.scalar(select(Branch).where(Branch.id == branch_id).with_for_update())
    if branch is None:
        raise NotFound()
    check_if_match(request, branch.version)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    clear = changes.pop("clear_location", False)
    _check_location_pair(changes.get("latitude"), changes.get("longitude"))
    if clear:
        changes["latitude"] = changes["longitude"] = None
    for key in ("latitude", "longitude"):
        if key in changes:
            changes[key] = _coord(changes[key])
    if "name" in changes:
        await _unique_branch_name(ctx, changes["name"], exclude=branch.id)
    if "timezone" in changes:
        workspaces.valid_timezone(changes["timezone"])
    if changes.get("require_admin_mfa") and ctx.user.totp_enabled_at is None:
        # Otherwise the person turning it on would lock themselves out.
        raise Invalid(
            "Turn on two-step verification for your own account first.",
            code="mfa_required_first",
            errors=[
                {"field": "require_admin_mfa", "message": "Turn on two-step verification for yourself first."}
            ],
        )
    if changes.get("is_active") is True and not branch.is_active:
        assert ctx.entitlements is not None
        limit = ctx.entitlements.plan.max_branches
        active = await ctx.db.scalar(
            select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))
        )
        if limit is not None and (active or 0) >= limit:
            raise PaymentRequired(f"Your plan includes {limit} branches.", code="branch_limit")
    if changes.get("is_active") is False and branch.is_active:
        others = await ctx.db.scalar(
            select(func.count()).select_from(Branch).where(Branch.is_active.is_(True), Branch.id != branch.id)
        )
        if not others:
            raise Conflict("Keep at least one branch open.", code="last_branch")
    before = {k: getattr(branch, k) for k in changes}
    for key, value in changes.items():
        setattr(branch, key, value)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "branch.updated",
        target_type="branch",
        target_id=branch.id,
        data={"before": before, "after": changes},
    )
    await ctx.db.commit()
    set_etag(response, branch.version)
    return BranchOut.model_validate(branch)


# ---- Audit log --------------------------------------------------------------------------


class AuditOut(Out):
    id: uuid.UUID
    seq: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    action: str
    target_type: str | None
    target_id: str | None
    data: dict[str, object]
    ip: str | None


class VerifyOut(Out):
    ok: bool
    first_bad_seq: int | None


@router.get("/audit", response_model=Page[AuditOut])
async def list_audit(
    ctx: Ctx = Depends(allow(AUDIT_VIEW)),
    action: Annotated[str | None, Query(max_length=100)] = None,
    target_type: Annotated[str | None, Query(max_length=50)] = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
    actor: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[AuditOut]:
    query = select(audit.AuditEvent, User.name).outerjoin(User, User.id == audit.AuditEvent.actor_user_id)
    if action:
        query = query.where(audit.AuditEvent.action.startswith(action))
    if target_type:
        query = query.where(audit.AuditEvent.target_type == target_type)
    if target_id:
        query = query.where(audit.AuditEvent.target_id == target_id)
    if actor:
        query = query.where(audit.AuditEvent.actor_user_id == actor)
    after = decode_cursor(cursor)
    if after:
        query = query.where(audit.AuditEvent.seq < int(after["seq"]))
    rows = (await ctx.db.execute(query.order_by(audit.AuditEvent.seq.desc()).limit(limit + 1))).all()
    items = [
        AuditOut(
            id=e.id,
            seq=e.seq,
            occurred_at=e.occurred_at,
            actor_user_id=e.actor_user_id,
            actor_name=e.actor_label or name,
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            data=e.data,
            ip=e.ip,
        )
        for e, name in rows[:limit]
    ]
    return Page(items=items, next_cursor=encode_cursor({"seq": items[-1].seq}) if len(rows) > limit else None)


@router.get("/audit/verify", response_model=VerifyOut)
async def verify_audit(ctx: Ctx = Depends(allow(AUDIT_VIEW))) -> VerifyOut:
    ok, bad = await audit.verify_chain(ctx.db)
    return VerifyOut(ok=ok, first_bad_seq=bad)
