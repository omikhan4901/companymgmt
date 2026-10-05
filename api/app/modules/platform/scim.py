"""SCIM 2.0 user provisioning (RFC 7643/7644), so a company's identity provider (Okta,
Microsoft Entra ID, JumpCloud, OneLogin) adds people when they're hired and removes them
when they leave.

Authenticate with an API key that holds `members.invite` and `members.manage` (made by
the owner or an admin). Plans with company sign-in only.

Mapping: a SCIM User is a membership of this workspace. `id` is the membership id,
`userName` and the primary email are the person's email, `active: false` (or DELETE)
removes them from the workspace and ends their sessions, `active: true` brings them back.
New people get the company sign-in's default role (or Employee) and sign in with the
company account. The owner can't be changed over SCIM. Groups aren't supported yet.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core import audit
from app.core.errors import AppError, Conflict, Forbidden, Invalid, NotFound, PaymentRequired
from app.core.time import utcnow
from app.modules.platform import catalog, hooks
from app.modules.platform.catalog import MEMBERS_INVITE, MEMBERS_MANAGE
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.models import Membership, Role, SsoConnection, User
from app.modules.platform.tokens import revoke_user_sessions

router = APIRouter(prefix="/scim/v2", tags=["scim"])

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
MEDIA = "application/scim+json"
MAX_COUNT = 200
FILTER = re.compile(r'^\s*(userName|emails(?:\.value)?|externalId)\s+eq\s+"([^"]{1,254})"\s*$', re.IGNORECASE)


async def scim_client(ctx: Ctx = Depends(allow(MEMBERS_MANAGE))) -> Ctx:
    ctx.require(MEMBERS_INVITE)
    assert ctx.entitlements is not None
    if not ctx.entitlements.feature("sso"):
        raise PaymentRequired("Provisioning isn't included in this plan.", code="feature_not_in_plan")
    return ctx


scim_client._access = "workspace"  # type: ignore[attr-defined]
scim_client._permission = MEMBERS_MANAGE  # type: ignore[attr-defined]
Client = Depends(scim_client)


def _scim(body: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, media_type=MEDIA)


def _error(exc: AppError) -> JSONResponse:
    return _scim({"schemas": [ERROR_SCHEMA], "status": str(exc.status), "detail": exc.detail}, exc.status)


def _resource(request: Request, member: Membership, user: User) -> dict[str, Any]:
    created: datetime = member.created_at
    return {
        "schemas": [USER_SCHEMA],
        "id": str(member.id),
        "externalId": member.external_id,
        "userName": user.email,
        "name": {"formatted": user.name},
        "displayName": user.name,
        "emails": [{"value": user.email, "primary": True, "type": "work"}] if user.email else [],
        "active": member.status == "active",
        "meta": {
            "resourceType": "User",
            "created": created.isoformat(),
            "lastModified": member.updated_at.isoformat(),
            "location": str(request.url_for("scim_get_user", user_id=str(member.id))),
            "version": f'W/"{member.version}"',
        },
    }


def _parse(body: dict[str, Any]) -> tuple[str, str, bool, str | None]:
    """(email, name, active, externalId) from a SCIM User."""
    emails = body.get("emails") or []
    primary = next((e for e in emails if isinstance(e, dict) and e.get("primary")), None)
    email = (
        str(body.get("userName") or (primary or (emails[0] if emails else {})).get("value") or "")
        .strip()
        .lower()
    )
    if "@" not in email or len(email) > 254:
        raise Invalid("userName must be the person's email address.", code="scim_invalid")
    name_part = body.get("name") or {}
    name = (
        body.get("displayName")
        or name_part.get("formatted")
        or " ".join(p for p in (name_part.get("givenName"), name_part.get("familyName")) if p)
        or email.split("@", 1)[0]
    )
    active = body.get("active", True)
    external = body.get("externalId")
    return email, str(name)[:120], bool(active), str(external)[:200] if external else None


async def _load(ctx: Ctx, user_id: str) -> tuple[Membership, User, Role]:
    try:
        member_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise NotFound() from exc
    row = (
        await ctx.db.execute(
            select(Membership, User, Role)
            .join(User, User.id == Membership.user_id)
            .join(Role, (Role.tenant_id == Membership.tenant_id) & (Role.id == Membership.role_id))
            .where(Membership.id == member_id)
            .with_for_update(of=Membership)
        )
    ).first()
    if row is None:
        raise NotFound()
    return row[0], row[1], row[2]


async def _default_role(ctx: Ctx) -> Role:
    connection = await ctx.db.get(SsoConnection, ctx.tenant_id)
    role = (
        await ctx.db.get(Role, connection.default_role_id)
        if connection and connection.default_role_id
        else None
    )
    if role is None or (role.is_builtin and role.key == "owner"):
        role = await ctx.db.scalar(
            select(Role).where(Role.is_builtin.is_(True), Role.key == catalog.DEFAULT_ROLE)
        )
    assert role is not None
    return role


async def _set_active(ctx: Ctx, member: Membership, user: User, role: Role, active: bool) -> None:
    if member.status == ("active" if active else "removed"):
        return
    if role.is_builtin and role.key == "owner":
        raise Forbidden("The workspace owner can't be changed by provisioning.", code="owner_protected")
    member.status = "active" if active else "removed"
    member.version += 1
    await ctx.db.flush()
    if active:
        await hooks.run(hooks.member_joined, ctx.db, member, user)
    else:
        await hooks.run(hooks.member_removed, ctx.db, member, user)
        await revoke_user_sessions(ctx.db, user.id, "member_removed", tenant_id=ctx.tenant_id)
    await audit.record(
        ctx.db,
        "member.restored_by_scim" if active else "member.removed_by_scim",
        target_type="member",
        target_id=member.id,
        data={"user": user.name},
    )


# ---- Discovery ----------------------------------------------------------------------------


@router.get("/ServiceProviderConfig")
async def service_provider_config(ctx: Ctx = Client) -> JSONResponse:
    return _scim(
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True},
            "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
            "filter": {"supported": True, "maxResults": MAX_COUNT},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": True},
            "authenticationSchemes": [
                {
                    "type": "oauthbearertoken",
                    "name": "API key",
                    "description": "Authorization: Bearer cmk_...",
                }
            ],
        }
    )


@router.get("/ResourceTypes")
async def resource_types(ctx: Ctx = Client) -> JSONResponse:
    return _scim(
        {
            "schemas": [LIST_SCHEMA],
            "totalResults": 1,
            "Resources": [
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                    "id": "User",
                    "name": "User",
                    "endpoint": "/Users",
                    "schema": USER_SCHEMA,
                }
            ],
        }
    )


# ---- Users --------------------------------------------------------------------------------


@router.get("/Users")
async def list_users(
    request: Request,
    filter: Annotated[str | None, Query(max_length=300)] = None,
    start_index: Annotated[int, Query(alias="startIndex", ge=1)] = 1,
    count: Annotated[int, Query(ge=0, le=MAX_COUNT)] = 100,
    ctx: Ctx = Client,
) -> JSONResponse:
    query = select(Membership, User).join(User, User.id == Membership.user_id).where(User.email.is_not(None))
    if filter:
        match = FILTER.match(filter)
        if match is None:
            return _error(
                Invalid('Only userName eq "...", emails eq "..." and externalId eq "..." are supported.')
            )
        attribute, value = match.group(1).lower(), match.group(2)
        if attribute == "externalid":
            query = query.where(Membership.external_id == value)
        else:
            query = query.where(func.lower(User.email) == value.lower())
    total = await ctx.db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await ctx.db.execute(query.order_by(Membership.created_at).offset(start_index - 1).limit(count))
    ).all()
    return _scim(
        {
            "schemas": [LIST_SCHEMA],
            "totalResults": int(total or 0),
            "startIndex": start_index,
            "itemsPerPage": len(rows),
            "Resources": [_resource(request, m, u) for m, u in rows],
        }
    )


@router.get("/Users/{user_id}", name="scim_get_user")
async def get_user(user_id: str, request: Request, ctx: Ctx = Client) -> JSONResponse:
    try:
        member, user, _role = await _load(ctx, user_id)
    except AppError as exc:
        return _error(exc)
    return _scim(_resource(request, member, user))


@router.post("/Users")
async def create_user(body: dict[str, Any], request: Request, ctx: Ctx = Client) -> JSONResponse:
    try:
        email, name, active, external = _parse(body)
        user = await ctx.db.scalar(
            select(User).where(func.lower(User.email) == email, User.managed_tenant_id.is_(None))
        )
        if user is not None:
            existing = await ctx.db.scalar(select(Membership).where(Membership.user_id == user.id))
            if existing is not None:
                raise Conflict("This person is already in the workspace.", code="scim_exists")
        else:
            user = User(email=email, email_verified_at=utcnow(), name=name, locale="en")
            ctx.db.add(user)
            await ctx.db.flush()
        role = await _default_role(ctx)
        member = Membership(user_id=user.id, role_id=role.id, external_id=external)
        ctx.db.add(member)
        await ctx.db.flush()
        await hooks.run(hooks.member_joined, ctx.db, member, user)
        await audit.record(
            ctx.db,
            "member.added_by_scim",
            target_type="member",
            target_id=member.id,
            data={"email": email, "role": role.key},
        )
        if not active:
            await _set_active(ctx, member, user, role, False)
        await ctx.db.commit()
        await ctx.db.refresh(member)
    except AppError as exc:
        await ctx.db.rollback()
        return _error(exc)
    return _scim(_resource(request, member, user), 201)


@router.put("/Users/{user_id}")
async def replace_user(
    user_id: str, body: dict[str, Any], request: Request, ctx: Ctx = Client
) -> JSONResponse:
    try:
        member, user, role = await _load(ctx, user_id)
        email, name, active, external = _parse(body)
        if user.email and email != user.email.lower():
            raise Invalid("Changing someone's email over SCIM isn't supported.", code="scim_email_change")
        user.name = name
        member.external_id = external
        member.version += 1
        await _set_active(ctx, member, user, role, active)
        await ctx.db.commit()
        await ctx.db.refresh(member)
    except AppError as exc:
        await ctx.db.rollback()
        return _error(exc)
    return _scim(_resource(request, member, user))


@router.patch("/Users/{user_id}")
async def patch_user(user_id: str, body: dict[str, Any], request: Request, ctx: Ctx = Client) -> JSONResponse:
    """The operations identity providers send: replace `active`, the name, `externalId`."""
    try:
        member, user, role = await _load(ctx, user_id)
        operations = body.get("Operations") or []
        if not isinstance(operations, list) or len(operations) > 50:
            raise Invalid("Send up to 50 operations.", code="scim_invalid")
        for op in operations:
            kind = str(op.get("op", "")).lower()
            if kind not in ("replace", "add"):
                raise Invalid(f"Unsupported operation {kind!r}.", code="scim_invalid")
            path = op.get("path")
            value = op.get("value")
            # Entra sends {"op": "replace", "value": {"active": false}} without a path.
            changes = value if path is None and isinstance(value, dict) else {path: value}
            for key, item in changes.items():
                lowered = str(key).lower()
                if lowered == "active":
                    active = item if isinstance(item, bool) else str(item).lower() == "true"
                    await _set_active(ctx, member, user, role, active)
                elif lowered in ("displayname", "name.formatted"):
                    user.name = str(item)[:120]
                elif lowered == "externalid":
                    member.external_id = str(item)[:200] if item else None
                elif lowered in ("name.givenname", "name.familyname", "name"):
                    continue
                else:
                    raise Invalid(f"Changing {key!r} isn't supported.", code="scim_invalid")
        member.version += 1
        await ctx.db.commit()
        await ctx.db.refresh(member)
    except AppError as exc:
        await ctx.db.rollback()
        return _error(exc)
    return _scim(_resource(request, member, user))


@router.delete("/Users/{user_id}", status_code=204, response_model=None)
async def delete_user(user_id: str, ctx: Ctx = Client) -> JSONResponse | None:
    """Removes them from the workspace (their account and history stay)."""
    try:
        member, user, role = await _load(ctx, user_id)
        await _set_active(ctx, member, user, role, False)
        await ctx.db.commit()
    except AppError as exc:
        await ctx.db.rollback()
        return _error(exc)
    return None
