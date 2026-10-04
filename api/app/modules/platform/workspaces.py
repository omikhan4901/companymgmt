"""Creating and configuring workspaces."""

from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from sqlalchemy import select, text
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


SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
RESERVED = frozenset(
    [
        "www",
        "app",
        "api",
        "admin",
        "administrator",
        "root",
        "mail",
        "email",
        "smtp",
        "imap",
        "pop",
        "ftp",
        "ns",
        "ns1",
        "ns2",
        "dns",
        "cdn",
        "static",
        "assets",
        "media",
        "files",
        "img",
        "images",
        "help",
        "support",
        "status",
        "docs",
        "developer",
        "developers",
        "dev",
        "staging",
        "test",
        "demo",
        "sandbox",
        "billing",
        "pay",
        "payment",
        "payments",
        "checkout",
        "invoice",
        "login",
        "logout",
        "signin",
        "signup",
        "register",
        "account",
        "accounts",
        "auth",
        "oauth",
        "sso",
        "saml",
        "scim",
        "webhook",
        "webhooks",
        "security",
        "trust",
        "legal",
        "privacy",
        "terms",
        "blog",
        "news",
        "about",
        "contact",
        "careers",
        "jobs",
        "team",
        "official",
        "verify",
        "verification",
        "secure",
        "internal",
        "system",
        "null",
        "undefined",
        "companymgmt",
        "company-mgmt",
        "companymanagement",
    ]
)
# Our own name with the usual swaps, so no workspace can pose as us.
LOOKALIKE = re.compile(r"c[o0]mpany[-_.]?m[a@]?n?[a@]?g?e?m?e?n?t|c[o0]mpanymgmt|cmpnymgmt")


def slug_problem(slug: str) -> str | None:
    if not SLUG.match(slug):
        return (
            "Use 3 to 40 lowercase letters, numbers and dashes, starting and ending with a letter or number."
        )
    if slug in RESERVED or slug.startswith("xn--") or LOOKALIKE.search(slug.replace("-", "")):
        return "This address is reserved. Choose another."
    if "--" in slug:
        return "Don't use two dashes in a row."
    return None


async def slug_taken(db: AsyncSession, slug: str, *, mine: uuid.UUID | None = None) -> bool:
    other = await db.scalar(select(Tenant.id).where(Tenant.slug == slug, Tenant.id != mine))
    if other:
        return True
    used = await db.scalar(select(Tenant.id).where(Tenant.previous_slugs.contains([slug]), Tenant.id != mine))
    return used is not None


async def unique_slug(db: AsyncSession, name: str) -> str:
    """A free address for a new workspace (never reserved, a look-alike, or used before)."""
    base = slugify(name)
    if slug_problem(base):
        base = (
            f"ws-{base[:20]}".strip("-")
            if not slug_problem(f"ws-{base[:20]}".strip("-"))
            else f"ws-{secrets.token_hex(3)}"
        )
    slug = base
    for _ in range(20):
        if not await slug_taken(db, slug):
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

    modules = catalog.preset_modules(business_type)
    db.add(
        Subscription(
            plan_key=BASE_PLAN,
            status="trialing",
            trial_plan_key=TRIAL_PLAN,
            trial_ends_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
            modules=modules,
        )
    )
    db.add(Branch(name="Main branch", timezone=tenant.timezone))
    membership = Membership(user_id=owner.id, role_id=roles["owner"].id)
    db.add(membership)
    await db.flush()
    await hooks.run(hooks.member_joined, db, membership, owner)
    await hooks.enable_modules(db, tenant, modules)
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
