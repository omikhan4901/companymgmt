"""Easy onboarding: the workspace's own address (`<slug>.companymgmt.app`), a public
lookup for that address, and join links (or QR codes) that let people make their own
staff account in the workspace.

Addresses are checked against a reserved list and look-alikes of our own name, and an
address a workspace gave up is never handed to another (no one can take over a link
people already trust). Join links carry a secret shown once; only its hash is kept.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, context, ratelimit
from app.core.db import get_db, set_tenant
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.schema import In, Name
from app.core.security import passwords
from app.core.security.tokens import hash_secret, new_secret
from app.core.time import utcnow
from app.modules.platform import hooks
from app.modules.platform.catalog import MEMBERS_INVITE, WORKSPACE_MANAGE
from app.modules.platform.deps import Ctx, allow, public
from app.modules.platform.models import JoinLink, Membership, Role, Tenant, User
from app.modules.platform.routes_workspace import _check_scope, _role_for_assignment
from app.modules.platform.workspaces import slug_problem, slug_taken

router = APIRouter(prefix="/v1", tags=["onboarding"])

JOIN_DAYS_MAX = 30


class AddressIn(In):
    slug: Annotated[str, StringConstraints(min_length=3, max_length=40, to_lower=True, strip_whitespace=True)]


class AddressOut(BaseModel):
    slug: str
    previous: list[str]


@router.put("/workspace/address", response_model=AddressOut)
async def change_address(body: AddressIn, ctx: Ctx = Depends(allow(WORKSPACE_MANAGE))) -> AddressOut:
    """The workspace's address and staff code. Only the owner can change it."""
    if not ctx.is_owner:
        raise Forbidden("Only the workspace owner can change its address.", code="owner_only")
    tenant = await ctx.db.scalar(select(Tenant).where(Tenant.id == ctx.tenant_id).with_for_update())
    assert tenant is not None
    if body.slug == tenant.slug:
        return AddressOut(slug=tenant.slug, previous=list(tenant.previous_slugs or []))
    problem = slug_problem(body.slug)
    if problem:
        raise Invalid(errors=[{"field": "slug", "message": problem}])
    if await slug_taken(ctx.db, body.slug, mine=tenant.id):
        raise Conflict("Another workspace has this address.", code="slug_taken")
    old = tenant.slug
    tenant.previous_slugs = [*dict.fromkeys([*(tenant.previous_slugs or []), old])][-10:]
    tenant.slug = body.slug
    await audit.record(
        ctx.db,
        "workspace.address_changed",
        target_type="workspace",
        target_id=tenant.id,
        data={"from": old, "to": body.slug},
    )
    await ctx.db.commit()
    return AddressOut(slug=tenant.slug, previous=list(tenant.previous_slugs or []))


class PublicWorkspaceOut(BaseModel):
    name: str
    slug: str
    locale: str
    # Set when the address asked for is an old one: send people to the current one.
    moved_to: str | None = None


@router.get("/public/workspace", response_model=PublicWorkspaceOut)
async def find_workspace(
    slug: Annotated[str, Query(min_length=3, max_length=40)],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> PublicWorkspaceOut:
    """What the sign-in page on `<slug>.companymgmt.app` shows (name only; nothing private)."""
    await ratelimit.enforce(ratelimit.LOGIN_IP, context.current().ip or "unknown")
    slug = slug.lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug, Tenant.status == "active"))
    moved = None
    if tenant is None:
        tenant = await db.scalar(
            select(Tenant).where(Tenant.previous_slugs.contains([slug]), Tenant.status == "active")
        )
        moved = tenant.slug if tenant else None
    if tenant is None:
        raise NotFound()
    return PublicWorkspaceOut(name=tenant.name, slug=tenant.slug, locale=tenant.locale, moved_to=moved)


# ---- Join links -----------------------------------------------------------------------


class JoinLinkIn(In):
    role_id: uuid.UUID
    scope_department_id: uuid.UUID | None = None
    label: Annotated[str | None, StringConstraints(max_length=120)] = None
    days: int = Field(default=7, ge=1, le=JOIN_DAYS_MAX)
    max_uses: int = Field(default=20, ge=1, le=500)


class JoinLinkOut(BaseModel):
    id: uuid.UUID
    hint: str
    label: str | None
    role_id: uuid.UUID
    role_name: str
    scope_department_id: uuid.UUID | None
    expires_at: datetime
    max_uses: int
    uses: int
    revoked: bool
    # Only when it's made: the token to put in the link (never shown again).
    token: str | None = None


def _link_out(link: JoinLink, role: str, token: str | None = None) -> JoinLinkOut:
    return JoinLinkOut(
        id=link.id,
        hint=link.hint,
        label=link.label,
        role_id=link.role_id,
        role_name=role,
        scope_department_id=link.scope_department_id,
        expires_at=link.expires_at,
        max_uses=link.max_uses,
        uses=link.uses,
        revoked=link.revoked_at is not None,
        token=token,
    )


@router.post("/join-links", response_model=JoinLinkOut, status_code=201)
async def create_link(body: JoinLinkIn, ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> JoinLinkOut:
    role = await _role_for_assignment(ctx, body.role_id)
    await _check_scope(ctx, body.scope_department_id)
    secret = new_secret(24)
    link = JoinLink(
        token_hash=hash_secret(secret),
        hint=secret[:6],
        label=body.label,
        role_id=role.id,
        scope_department_id=body.scope_department_id,
        expires_at=utcnow() + timedelta(days=body.days),
        max_uses=body.max_uses,
        created_by=ctx.user.id,
    )
    ctx.db.add(link)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "join_link.created",
        target_type="join_link",
        target_id=link.id,
        data={"role": role.key, "days": body.days, "max_uses": body.max_uses},
    )
    await ctx.db.commit()
    return _link_out(link, role.name, token=f"{ctx.tenant_id}.{secret}")


@router.get("/join-links", response_model=list[JoinLinkOut])
async def list_links(ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> list[JoinLinkOut]:
    rows = (
        await ctx.db.execute(
            select(JoinLink, Role.name)
            .join(Role, Role.id == JoinLink.role_id)
            .order_by(JoinLink.created_at.desc())
        )
    ).all()
    return [_link_out(link, role) for link, role in rows]


@router.delete("/join-links/{link_id}", status_code=204)
async def revoke_link(link_id: uuid.UUID, ctx: Ctx = Depends(allow(MEMBERS_INVITE))) -> None:
    link = await ctx.db.scalar(select(JoinLink).where(JoinLink.id == link_id).with_for_update())
    if link is None:
        raise NotFound()
    if link.revoked_at is None:
        link.revoked_at = utcnow()
        await audit.record(ctx.db, "join_link.revoked", target_type="join_link", target_id=link.id, data={})
        await ctx.db.commit()


async def _open_link(db: AsyncSession, token: str) -> tuple[JoinLink, Tenant, Role]:
    tenant_part, _, secret = token.partition(".")
    try:
        tenant_id = uuid.UUID(tenant_part)
    except ValueError as exc:
        raise Invalid("This link isn't valid.", code="join_invalid") from exc
    await set_tenant(db, tenant_id)
    link = await db.scalar(
        select(JoinLink).where(JoinLink.token_hash == hash_secret(secret)).with_for_update()
    )
    if link is None or link.revoked_at is not None:
        raise Invalid("This link isn't valid any more. Ask for a new one.", code="join_invalid")
    if link.expires_at <= utcnow():
        raise Invalid("This link expired. Ask for a new one.", code="join_expired")
    if link.uses >= link.max_uses:
        raise Invalid(
            "This link has been used as many times as allowed. Ask for a new one.", code="join_used_up"
        )
    tenant = await db.get(Tenant, tenant_id)
    role = await db.get(Role, link.role_id)
    if tenant is None or tenant.status != "active" or role is None:
        raise Invalid("This link isn't valid any more.", code="join_invalid")
    return link, tenant, role


class JoinLookupOut(BaseModel):
    workspace: str
    workspace_code: str
    role: str


@router.get("/join/lookup", response_model=JoinLookupOut)
async def lookup_link(
    token: Annotated[str, Query(max_length=200)],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(public()),
) -> JoinLookupOut:
    await ratelimit.enforce(ratelimit.RESET_IP, context.current().ip or "unknown")
    _link, tenant, role = await _open_link(db, token)
    return JoinLookupOut(workspace=tenant.name, workspace_code=tenant.slug, role=role.name)


class JoinIn(In):
    token: Annotated[str, StringConstraints(max_length=200)]
    name: Name
    username: Annotated[
        str, StringConstraints(min_length=3, max_length=40, pattern=r"^[a-z0-9._-]+$", to_lower=True)
    ]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class JoinOut(BaseModel):
    workspace_code: str
    username: str


@router.post("/join", response_model=JoinOut, status_code=201)
async def join(body: JoinIn, db: AsyncSession = Depends(get_db), _: None = Depends(public())) -> JoinOut:
    """Make your own staff account from a join link, then sign in with it."""
    await ratelimit.enforce(ratelimit.RESET_IP, context.current().ip or "unknown")
    link, tenant, role = await _open_link(db, body.token)
    taken = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.managed_tenant_id == tenant.id, func.lower(User.username) == body.username)
    )
    if taken:
        raise Invalid(errors=[{"field": "username", "message": "This username is taken in this workspace."}])
    issues = passwords.problems(body.password, context=(body.name, body.username))
    if issues:
        raise Invalid(errors=[{"field": "password", "message": m} for m in issues])
    now = utcnow()
    user = User(
        name=body.name,
        username=body.username,
        managed_tenant_id=tenant.id,
        password_hash=passwords.hash_password(body.password),
        password_changed_at=now,
        must_change_password=False,
        locale=tenant.locale,
    )
    db.add(user)
    await db.flush()
    await set_tenant(db, tenant.id, user.id)
    member = Membership(user_id=user.id, role_id=role.id, scope_department_id=link.scope_department_id)
    db.add(member)
    await db.flush()
    link.uses += 1
    await hooks.run(hooks.member_joined, db, member, user)
    await audit.record(
        db,
        "member.joined_by_link",
        target_type="member",
        target_id=member.id,
        data={"name": body.name, "link": str(link.id)},
        actor_user_id=user.id,
    )
    await db.commit()
    return JoinOut(workspace_code=tenant.slug, username=body.username)
