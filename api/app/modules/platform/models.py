"""Platform tables: workspaces (tenants), plans, users, sessions, roles, members, invites,
branches.

Global tables (no tenant_id): tenants, plans, users and the auth tables. They are only read
through code paths that already know which user or tenant they're for. Tenant tables are
protected by row-level security.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned


class Plan(Base):
    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    price_month_cents: Mapped[int | None] = mapped_column(Integer)
    price_year_cents: Mapped[int | None] = mapped_column(Integer)
    included_people: Mapped[int | None] = mapped_column(Integer)
    extra_person_cents: Mapped[int | None] = mapped_column(Integer)
    # None means unlimited.
    max_people: Mapped[int | None] = mapped_column(Integer)
    max_branches: Mapped[int | None] = mapped_column(Integer)
    max_modules: Mapped[int | None] = mapped_column(Integer)
    storage_mb: Mapped[int | None] = mapped_column(Integer)
    audit_retention_days: Mapped[int | None] = mapped_column(Integer)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sort: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)


class Tenant(IdMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$'", name="slug_format"),
        CheckConstraint("status IN ('active', 'suspended', 'deleting')", name="status"),
        CheckConstraint("ui_mode IN ('simple', 'standard', 'advanced')", name="ui_mode"),
    )

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    business_type: Mapped[str] = mapped_column(String(30))
    ui_mode: Mapped[str] = mapped_column(String(10), default="standard")
    country: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    locale: Mapped[str] = mapped_column(String(10), default="en")
    week_start: Mapped[int] = mapped_column(SmallInteger, default=1)
    fiscal_year_start_month: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(String(10), default="active")
    deletion_requested_at: Mapped[datetime | None]
    # Who asked, so the deletion certificate can reach them after everything else is gone.
    deletion_contact: Mapped[str | None] = mapped_column(String(254))
    # Owners and admins must use two-step verification.
    require_admin_mfa: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Subscription(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'read_only', 'canceled')", name="status"
        ),
    )

    plan_key: Mapped[str] = mapped_column(ForeignKey("plans.key"))
    status: Mapped[str] = mapped_column(String(12))
    trial_plan_key: Mapped[str | None] = mapped_column(ForeignKey("plans.key"))
    trial_ends_at: Mapped[datetime | None]
    current_period_end: Mapped[datetime | None]
    modules: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)
    provider: Mapped[str] = mapped_column(String(20), default="none")
    provider_ref: Mapped[str | None] = mapped_column(String(100))


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_email",
            func.lower(text("email")),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_users_managed_username",
            "managed_tenant_id",
            func.lower(text("username")),
            unique=True,
            postgresql_where=text("managed_tenant_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(email IS NOT NULL AND managed_tenant_id IS NULL) OR "
            "(managed_tenant_id IS NOT NULL AND username IS NOT NULL)",
            name="login_identity",
        ),
    )

    email: Mapped[str | None] = mapped_column(String(254))
    email_verified_at: Mapped[datetime | None]
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(200))
    password_changed_at: Mapped[datetime | None]
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    locale: Mapped[str] = mapped_column(String(10), default="en")
    # Staff accounts without email belong to one workspace and sign in with a username.
    managed_tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"))
    username: Mapped[str | None] = mapped_column(String(40))
    totp_secret_enc: Mapped[str | None] = mapped_column(String(300))
    totp_pending_enc: Mapped[str | None] = mapped_column(String(300))
    totp_enabled_at: Mapped[datetime | None]
    totp_last_step: Mapped[int | None]
    disabled_at: Mapped[datetime | None]


class AuthSession(IdMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    mfa_at: Mapped[datetime | None]
    reauth_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    revoke_reason: Mapped[str | None] = mapped_column(String(40))


class RefreshToken(IdMixin, Base):
    __tablename__ = "refresh_tokens"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth_sessions.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class AuthChallenge(IdMixin, Base):
    """Password was right; the second factor is still needed."""

    __tablename__ = "auth_challenges"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    tenant_hint: Mapped[uuid.UUID | None]
    expires_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    used_at: Mapped[datetime | None]


class RecoveryCode(IdMixin, Base):
    __tablename__ = "recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None]


class EmailToken(IdMixin, Base):
    __tablename__ = "email_tokens"
    __table_args__ = (CheckConstraint("purpose IN ('verify', 'reset')", name="purpose"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(10))
    email: Mapped[str] = mapped_column(String(254))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class AuthEvent(IdMixin, Base):
    """Security events about a user (sign-ins, failures, MFA, resets). Append-only."""

    __tablename__ = "auth_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Role(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "key"),
    )

    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(String(300))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Custom roles only; built-in roles take their permissions from code.
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)


class Membership(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id"),
        ForeignKeyConstraint(["tenant_id", "role_id"], ["roles.tenant_id", "roles.id"]),
        CheckConstraint("status IN ('active', 'disabled', 'removed')", name="status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(String(10), default="active")
    # Limits scoped permissions to this department and its sub-departments.
    scope_department_id: Mapped[uuid.UUID | None]


class Invite(IdMixin, TenantScoped, Base):
    __tablename__ = "invites"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "role_id"], ["roles.tenant_id", "roles.id"]),
    )

    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str | None] = mapped_column(String(120))
    role_id: Mapped[uuid.UUID]
    scope_department_id: Mapped[uuid.UUID | None]
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class Branch(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index("uq_branches_name", "tenant_id", func.lower(text("name")), unique=True),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="location_pair"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude"),
        CheckConstraint("geofence_m BETWEEN 25 AND 5000", name="geofence"),
    )

    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_on: Mapped[date | None] = mapped_column(Date)
    # Where the branch is, for location-checked clock-ins. Unset until someone places it.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # Radius around the branch that counts as "at work", in metres.
    geofence_m: Mapped[int] = mapped_column(Integer, default=150, server_default="150")
