"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-30 14:43:37.965685
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations import rls

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    rls.install_functions()
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_label", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_audit_events_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "seq", name=op.f("uq_audit_events_tenant_id_seq")),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"], unique=False)
    op.create_table(
        "branches",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_branches_tenant_id_id")),
    )
    op.create_index(op.f("ix_branches_tenant_id"), "branches", ["tenant_id"], unique=False)
    op.create_index(
        "uq_branches_name", "branches", ["tenant_id", sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "departments",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id", name=op.f("ck_departments_not_own_parent")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "parent_id"],
            ["departments.tenant_id", "departments.id"],
            name=op.f("fk_departments_tenant_id_parent_id_departments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_departments_tenant_id_id")),
    )
    op.create_index(op.f("ix_departments_tenant_id"), "departments", ["tenant_id"], unique=False)
    op.create_index(
        "uq_departments_sibling_name",
        "departments",
        [
            "tenant_id",
            sa.literal_column("coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            sa.literal_column("lower(name)"),
        ],
        unique=True,
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(op.f("ix_outbox_events_available_at"), "outbox_events", ["available_at"], unique=False)
    op.create_index(op.f("ix_outbox_events_dispatched_at"), "outbox_events", ["dispatched_at"], unique=False)
    op.create_table(
        "plans",
        sa.Column("key", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("price_month_cents", sa.Integer(), nullable=True),
        sa.Column("price_year_cents", sa.Integer(), nullable=True),
        sa.Column("included_people", sa.Integer(), nullable=True),
        sa.Column("extra_person_cents", sa.Integer(), nullable=True),
        sa.Column("max_people", sa.Integer(), nullable=True),
        sa.Column("max_branches", sa.Integer(), nullable=True),
        sa.Column("max_modules", sa.Integer(), nullable=True),
        sa.Column("storage_mb", sa.Integer(), nullable=True),
        sa.Column("audit_retention_days", sa.Integer(), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort", sa.SmallInteger(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_plans")),
    )
    op.create_table(
        "rate_limits",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_rate_limits")),
        prefixes=["UNLOGGED"],
    )
    op.create_table(
        "roles",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("permissions", sa.ARRAY(sa.String(length=60)), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_roles_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "key", name=op.f("uq_roles_tenant_id_key")),
    )
    op.create_index(op.f("ix_roles_tenant_id"), "roles", ["tenant_id"], unique=False)
    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("business_type", sa.String(length=30), nullable=False),
        sa.Column("ui_mode", sa.String(length=10), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("week_start", sa.SmallInteger(), nullable=False),
        sa.Column("fiscal_year_start_month", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$'", name=op.f("ck_tenants_slug_format")
        ),
        sa.CheckConstraint("status IN ('active', 'suspended', 'deleting')", name=op.f("ck_tenants_status")),
        sa.CheckConstraint("ui_mode IN ('simple', 'standard', 'advanced')", name=op.f("ck_tenants_ui_mode")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_table(
        "subscriptions",
        sa.Column("plan_key", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("trial_plan_key", sa.String(length=30), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modules", sa.ARRAY(sa.String(length=30)), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'read_only', 'canceled')",
            name=op.f("ck_subscriptions_status"),
        ),
        sa.ForeignKeyConstraint(["plan_key"], ["plans.key"], name=op.f("fk_subscriptions_plan_key_plans")),
        sa.ForeignKeyConstraint(
            ["trial_plan_key"], ["plans.key"], name=op.f("fk_subscriptions_trial_plan_key_plans")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_subscriptions_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_subscriptions_tenant_id")),
    )
    op.create_index(op.f("ix_subscriptions_tenant_id"), "subscriptions", ["tenant_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("managed_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("username", sa.String(length=40), nullable=True),
        sa.Column("totp_secret_enc", sa.String(length=300), nullable=True),
        sa.Column("totp_pending_enc", sa.String(length=300), nullable=True),
        sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totp_last_step", sa.Integer(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(email IS NOT NULL AND managed_tenant_id IS NULL) OR (managed_tenant_id IS NOT NULL AND username IS NOT NULL)",
            name=op.f("ck_users_login_identity"),
        ),
        sa.ForeignKeyConstraint(
            ["managed_tenant_id"], ["tenants.id"], name=op.f("fk_users_managed_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "uq_users_managed_username",
        "users",
        ["managed_tenant_id", sa.literal_column("lower(username)")],
        unique=True,
        postgresql_where=sa.text("managed_tenant_id IS NOT NULL"),
    )
    op.create_table(
        "auth_challenges",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_hint", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_challenges_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_challenges")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_challenges_token_hash")),
    )
    op.create_table(
        "auth_events",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_events_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_events")),
    )
    op.create_index(op.f("ix_auth_events_user_id"), "auth_events", ["user_id"], unique=False)
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("mfa_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reauth_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_auth_sessions_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "email_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("purpose IN ('verify', 'reset')", name=op.f("ck_email_tokens_purpose")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_email_tokens_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)
    op.create_table(
        "invites",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("scope_department_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], name=op.f("fk_invites_invited_by_users")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            name=op.f("fk_invites_tenant_id_role_id_roles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_invites_tenant_id_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
    )
    op.create_index(op.f("ix_invites_tenant_id"), "invites", ["tenant_id"], unique=False)
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("scope_department_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled', 'removed')", name=op.f("ck_memberships_status")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            name=op.f("fk_memberships_tenant_id_role_id_roles"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_memberships_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "user_id", name=op.f("uq_memberships_tenant_id_user_id")),
    )
    op.create_index(op.f("ix_memberships_tenant_id"), "memberships", ["tenant_id"], unique=False)
    op.create_table(
        "recovery_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_recovery_codes_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_codes")),
    )
    op.create_index(op.f("ix_recovery_codes_user_id"), "recovery_codes", ["user_id"], unique=False)
    op.create_table(
        "employees",
        sa.Column("membership_id", sa.Uuid(), nullable=True),
        sa.Column("employee_code", sa.String(length=40), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("preferred_name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("employment_type", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=True),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("national_id_enc", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "employment_type IN ('full_time', 'part_time', 'contract', 'intern', 'daily')",
            name=op.f("ck_employees_employment_type"),
        ),
        sa.CheckConstraint("status IN ('active', 'inactive', 'left')", name=op.f("ck_employees_status")),
        sa.CheckConstraint(
            "left_on IS NULL OR joined_on IS NULL OR left_on >= joined_on", name=op.f("ck_employees_dates")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["branches.tenant_id", "branches.id"],
            name=op.f("fk_employees_tenant_id_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "department_id"],
            ["departments.tenant_id", "departments.id"],
            name=op.f("fk_employees_tenant_id_department_id_departments"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["memberships.tenant_id", "memberships.id"],
            name=op.f("fk_employees_tenant_id_membership_id_memberships"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_employees_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "membership_id", name=op.f("uq_employees_tenant_id_membership_id")),
    )
    op.create_index(op.f("ix_employees_tenant_id"), "employees", ["tenant_id"], unique=False)
    op.create_index(
        "ix_employees_tenant_name",
        "employees",
        ["tenant_id", sa.literal_column("lower(full_name)")],
        unique=False,
    )
    op.create_index(
        "uq_employees_code",
        "employees",
        ["tenant_id", sa.literal_column("lower(employee_code)")],
        unique=True,
        postgresql_where=sa.text("employee_code IS NOT NULL"),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["auth_sessions.id"], name=op.f("fk_refresh_tokens_session_id_auth_sessions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_session_id"), "refresh_tokens", ["session_id"], unique=False)
    op.create_table(
        "attendance_records",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("clock_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("client_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        postgresql.ExcludeConstraint(
            (sa.column("tenant_id"), "="),
            (sa.column("employee_id"), "="),
            (sa.text("tstzrange(clock_in_at, coalesce(clock_out_at, 'infinity'), '[)')"), "&&"),
            using="gist",
            name="no_overlap",
        ),
        sa.CheckConstraint(
            "clock_out_at IS NULL OR clock_out_at - clock_in_at <= interval '24 hours'",
            name=op.f("ck_attendance_records_max_length"),
        ),
        sa.CheckConstraint(
            "source IN ('self', 'kiosk', 'manual', 'correction')", name=op.f("ck_attendance_records_source")
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'auto_closed')", name=op.f("ck_attendance_records_status")
        ),
        sa.CheckConstraint(
            "clock_out_at IS NULL OR clock_out_at > clock_in_at", name=op.f("ck_attendance_records_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_attendance_records_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["branches.tenant_id", "branches.id"],
            name=op.f("fk_attendance_records_tenant_id_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["employees.tenant_id", "employees.id"],
            name=op.f("fk_attendance_records_tenant_id_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_records")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_attendance_records_tenant_id_id")),
    )
    op.create_index("ix_attendance_date", "attendance_records", ["tenant_id", "business_date"], unique=False)
    op.create_index(
        "ix_attendance_employee_date",
        "attendance_records",
        ["tenant_id", "employee_id", "business_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_attendance_records_tenant_id"), "attendance_records", ["tenant_id"], unique=False
    )
    op.create_index(
        "uq_attendance_open",
        "attendance_records",
        ["tenant_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("clock_out_at IS NULL"),
    )
    op.create_table(
        "attendance_corrections",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("proposed_clock_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed_clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('add', 'change', 'remove')", name=op.f("ck_attendance_corrections_kind")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_attendance_corrections_status"),
        ),
        sa.CheckConstraint(
            "proposed_clock_out_at IS NULL OR proposed_clock_out_at > proposed_clock_in_at",
            name=op.f("ck_attendance_corrections_order"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["users.id"], name=op.f("fk_attendance_corrections_decided_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_attendance_corrections_requested_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "employee_id"],
            ["employees.tenant_id", "employees.id"],
            name=op.f("fk_attendance_corrections_tenant_id_employee_id_employees"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "record_id"],
            ["attendance_records.tenant_id", "attendance_records.id"],
            name=op.f("fk_attendance_corrections_tenant_id_record_id_attendance_records"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_corrections")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_attendance_corrections_tenant_id_id")),
    )
    op.create_index(
        op.f("ix_attendance_corrections_tenant_id"), "attendance_corrections", ["tenant_id"], unique=False
    )
    op.create_index("ix_corrections_status", "attendance_corrections", ["tenant_id", "status"], unique=False)

    for table in (
        "subscriptions",
        "roles",
        "memberships",
        "invites",
        "branches",
        "departments",
        "employees",
        "attendance_records",
        "attendance_corrections",
    ):
        rls.tenant_table(table)
    rls.tenant_table("audit_events", privileges="SELECT, INSERT")
    rls.append_only("audit_events")

    rls.global_table("plans", privileges="SELECT")
    rls.global_table("tenants", privileges="SELECT, INSERT, UPDATE")
    rls.global_table("users", privileges="SELECT, INSERT, UPDATE")
    rls.global_table("auth_sessions", privileges="SELECT, INSERT, UPDATE")
    # Short-lived rows the daily maintenance job deletes.
    for table in ("refresh_tokens", "auth_challenges", "email_tokens", "outbox_events", "recovery_codes"):
        rls.global_table(table)
    rls.global_table("rate_limits")
    rls.global_table("auth_events", privileges="SELECT, INSERT")
    rls.append_only("auth_events")

    # The one controlled cross-tenant read: the workspaces a signed-in user belongs to.
    # It runs as the owner, which may read memberships and roles through a SELECT-only
    # policy. The app role never gets that policy.
    owner = "current_user"
    op.execute(f"CREATE POLICY owner_read ON memberships FOR SELECT TO {owner} USING (true)")
    op.execute(f"CREATE POLICY owner_read ON roles FOR SELECT TO {owner} USING (true)")
    op.execute(
        """
        CREATE FUNCTION app_user_workspaces(p_user uuid)
        RETURNS TABLE (tenant_id uuid, name text, slug text, role_key text, role_name text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
        $$ SELECT t.id, t.name::text, t.slug::text, r.key::text, r.name::text
           FROM memberships m
           JOIN tenants t ON t.id = m.tenant_id
           JOIN roles r ON r.tenant_id = m.tenant_id AND r.id = m.role_id
           WHERE m.user_id = p_user AND m.status = 'active' AND t.status <> 'deleting'
           ORDER BY t.name $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_user_workspaces(uuid) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_user_workspaces(uuid) TO {rls.app_role()}")

    plans = sa.table(
        "plans",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("price_month_cents", sa.Integer),
        sa.column("price_year_cents", sa.Integer),
        sa.column("included_people", sa.Integer),
        sa.column("extra_person_cents", sa.Integer),
        sa.column("max_people", sa.Integer),
        sa.column("max_branches", sa.Integer),
        sa.column("max_modules", sa.Integer),
        sa.column("storage_mb", sa.Integer),
        sa.column("audit_retention_days", sa.Integer),
        sa.column("features", postgresql.JSONB),
        sa.column("sort", sa.SmallInteger),
        sa.column("is_public", sa.Boolean),
    )
    op.bulk_insert(
        plans,
        [
            dict(
                key="free",
                name="Free",
                price_month_cents=0,
                price_year_cents=0,
                included_people=5,
                extra_person_cents=None,
                max_people=5,
                max_branches=1,
                max_modules=2,
                storage_mb=200,
                audit_retention_days=30,
                features={"custom_roles": False, "approvals": "none", "api": False, "sso": False},
                sort=0,
                is_public=True,
            ),
            dict(
                key="starter",
                name="Starter",
                price_month_cents=900,
                price_year_cents=9000,
                included_people=15,
                extra_person_cents=None,
                max_people=15,
                max_branches=1,
                max_modules=4,
                storage_mb=1024,
                audit_retention_days=90,
                features={"custom_roles": False, "approvals": "none", "api": False, "sso": False},
                sort=1,
                is_public=True,
            ),
            dict(
                key="growth",
                name="Growth",
                price_month_cents=2900,
                price_year_cents=29000,
                included_people=50,
                extra_person_cents=None,
                max_people=50,
                max_branches=3,
                max_modules=None,
                storage_mb=10240,
                audit_retention_days=365,
                features={"custom_roles": True, "approvals": "single", "api": False, "sso": False},
                sort=2,
                is_public=True,
            ),
            dict(
                key="business",
                name="Business",
                price_month_cents=7900,
                price_year_cents=79000,
                included_people=150,
                extra_person_cents=150,
                max_people=None,
                max_branches=None,
                max_modules=None,
                storage_mb=51200,
                audit_retention_days=1095,
                features={"custom_roles": True, "approvals": "multi", "api": True, "sso": False},
                sort=3,
                is_public=True,
            ),
            dict(
                key="enterprise",
                name="Enterprise",
                price_month_cents=None,
                price_year_cents=None,
                included_people=None,
                extra_person_cents=None,
                max_people=None,
                max_branches=None,
                max_modules=None,
                storage_mb=None,
                audit_retention_days=None,
                features={"custom_roles": True, "approvals": "multi", "api": True, "sso": True},
                sort=4,
                is_public=True,
            ),
        ],
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_user_workspaces(uuid)")
    op.drop_index("ix_corrections_status", table_name="attendance_corrections")
    op.drop_index(op.f("ix_attendance_corrections_tenant_id"), table_name="attendance_corrections")
    op.drop_table("attendance_corrections")
    op.drop_index(
        "uq_attendance_open",
        table_name="attendance_records",
        postgresql_where=sa.text("clock_out_at IS NULL"),
    )
    op.drop_index(op.f("ix_attendance_records_tenant_id"), table_name="attendance_records")
    op.drop_index("ix_attendance_employee_date", table_name="attendance_records")
    op.drop_index("ix_attendance_date", table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_index(op.f("ix_refresh_tokens_session_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(
        "uq_employees_code", table_name="employees", postgresql_where=sa.text("employee_code IS NOT NULL")
    )
    op.drop_index("ix_employees_tenant_name", table_name="employees")
    op.drop_index(op.f("ix_employees_tenant_id"), table_name="employees")
    op.drop_table("employees")
    op.drop_index(op.f("ix_recovery_codes_user_id"), table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_index(op.f("ix_memberships_tenant_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_invites_tenant_id"), table_name="invites")
    op.drop_table("invites")
    op.drop_index(op.f("ix_email_tokens_user_id"), table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(op.f("ix_auth_events_user_id"), table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_table("auth_challenges")
    op.drop_index(
        "uq_users_managed_username",
        table_name="users",
        postgresql_where=sa.text("managed_tenant_id IS NOT NULL"),
    )
    op.drop_index("uq_users_email", table_name="users", postgresql_where=sa.text("email IS NOT NULL"))
    op.drop_table("users")
    op.drop_index(op.f("ix_subscriptions_tenant_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("tenants")
    op.drop_index(op.f("ix_roles_tenant_id"), table_name="roles")
    op.drop_table("roles")
    op.drop_table("rate_limits")
    op.drop_table("plans")
    op.drop_index(op.f("ix_outbox_events_dispatched_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_available_at"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("uq_departments_sibling_name", table_name="departments")
    op.drop_index(op.f("ix_departments_tenant_id"), table_name="departments")
    op.drop_table("departments")
    op.drop_index("uq_branches_name", table_name="branches")
    op.drop_index(op.f("ix_branches_tenant_id"), table_name="branches")
    op.drop_table("branches")
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION IF EXISTS app_forbid_change() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS app_current_tenant()")
