"""Creating and configuring workspaces."""

from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.db import set_tenant
from app.core.errors import Invalid
from app.modules.platform import catalog, hooks
from app.modules.platform.models import Branch, Membership, Role, Subscription, Tenant, User

TRIAL_DAYS = 14
TRIAL_PLAN = "growth"
BASE_PLAN = "free"

# Sensible default currency for common countries; anything else can be chosen in settings.
COUNTRY_CURRENCY = {
    "BD": "BDT",
    "IN": "INR",
    "PK": "PKR",
    "LK": "LKR",
    "NP": "NPR",
    "US": "USD",
    "GB": "GBP",
    "CA": "CAD",
    "AU": "AUD",
    "AE": "AED",
    "SA": "SAR",
    "MY": "MYR",
    "SG": "SGD",
    "ID": "IDR",
    "PH": "PHP",
    "NG": "NGN",
    "KE": "KES",
    "ZA": "ZAR",
    "JP": "JPY",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "NL": "EUR",
    "IE": "EUR",
}


def valid_timezone(name: str) -> str:
    if name not in available_timezones():
        raise Invalid(errors=[{"field": "timezone", "message": "Unknown timezone."}])
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise Invalid(errors=[{"field": "timezone", "message": "Unknown timezone."}]) from exc
    return name


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:30].strip("-")
    return slug if len(slug) >= 3 else f"ws-{secrets.token_hex(3)}"


async def unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)
    slug = base
    for _ in range(20):
        taken = await db.scalar(select(func.count()).select_from(Tenant).where(Tenant.slug == slug))
        if not taken:
            return slug
        slug = f"{base[:33]}-{secrets.token_hex(2)}"
    return f"ws-{secrets.token_hex(6)}"


async def create_workspace(
    db: AsyncSession,
    owner: User,
    *,
    name: str,
    business_type: str,
    country: str | None,
    timezone: str,
    currency: str | None,
    locale: str,
) -> Tenant:
    ui_mode, _ = catalog.BUSINESS_TYPES.get(business_type, catalog.BUSINESS_TYPES["other"])
    tenant = Tenant(
        name=name,
        slug=await unique_slug(db, name),
        business_type=business_type,
        ui_mode=ui_mode,
        country=country,
        currency=currency or COUNTRY_CURRENCY.get(country or "", "USD"),
        timezone=valid_timezone(timezone),
        locale=locale,
        fiscal_year_start_month=7 if country == "BD" else 1,
        week_start=6 if country == "BD" else 1,
    )
    db.add(tenant)
    await db.flush()
    await set_tenant(db, tenant.id, owner.id)

    roles: dict[str, Role] = {}
    for r in catalog.BUILTIN_ROLES:
        role = Role(key=r.key, name=r.name, description=r.description, is_builtin=True)
        db.add(role)
        roles[r.key] = role
    await db.flush()

    db.add(
        Subscription(
            plan_key=BASE_PLAN,
            status="trialing",
            trial_plan_key=TRIAL_PLAN,
            trial_ends_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
            modules=catalog.preset_modules(business_type),
        )
    )
    db.add(Branch(name="Main branch", timezone=tenant.timezone))
    membership = Membership(user_id=owner.id, role_id=roles["owner"].id)
    db.add(membership)
    await db.flush()
    await hooks.run(hooks.member_joined, db, membership, owner)
    await audit.record(
        db,
        "workspace.created",
        target_type="workspace",
        target_id=tenant.id,
        data={"name": name, "business_type": business_type},
        actor_user_id=owner.id,
    )
    return tenant


async def user_workspaces(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, str]]:
    rows = await db.execute(
        text("SELECT tenant_id, name, slug, role_key, role_name FROM app_user_workspaces(:u)"),
        {"u": user_id},
    )
    return [{"id": str(r.tenant_id), "name": r.name, "slug": r.slug, "role": r.role_name} for r in rows]
