"""Nightly maintenance that needs the database owner's rights, so it runs as its own Cloud
Run Job (the API itself never holds them):

- purge workspaces whose 30-day deletion grace period has ended, and queue a signed
  deletion certificate to the person who asked;
- delete audit entries older than the workspace plan's retention, leaving an anchor so the
  rest of the chain still verifies.

    python -m app.jobs.maintenance
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.core.ids import uuid7
from app.core.models import Base, TenantScoped
from app.core.security.tokens import _keys
from app.models_registry import metadata
from app.modules.platform.deps import DELETION_GRACE

log = logging.getLogger("app.jobs.maintenance")

# Global tables that point at a workspace or a user and must be cleaned up with it.
SESSION_CHILDREN = ("refresh_tokens",)
USER_CHILDREN = ("auth_challenges", "recovery_codes", "email_tokens", "auth_events")


def _tenant_tables() -> list[str]:
    """Tables of TenantScoped models (not global ones that merely mention a workspace),
    children before parents, so deletes never break a foreign key."""
    scoped = {
        str(getattr(m.class_, "__tablename__", ""))
        for m in Base.registry.mappers
        if issubclass(m.class_, TenantScoped)
    }
    return [t.name for t in reversed(metadata.sorted_tables) if t.name in scoped]


def _bind(conn: psycopg.Connection, tenant_id: uuid.UUID) -> None:
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
    conn.execute("SELECT set_config('app.allow_purge', 'on', true)")


def sign(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    private, _ = _keys()
    return base64.urlsafe_b64encode(private.sign(body)).decode().rstrip("=")


def _certificate_mail(cert: dict[str, Any], signature: str, to: str, locale: str) -> dict[str, Any]:
    rows = "\n".join(f"  {table}: {count}" for table, count in sorted(cert["rows"].items()) if count)
    if locale == "bn":
        subject = f"{cert['name']} মুছে ফেলার সনদ"
        intro = f"{cert['name']} এবং এর সব তথ্য স্থায়ীভাবে মুছে ফেলা হয়েছে।"
    else:
        subject = f"Deletion certificate for {cert['name']}"
        intro = f"{cert['name']} and everything in it has been permanently deleted."
    text = (
        f"{intro}\n\n"
        f"Workspace: {cert['workspace_id']}\n"
        f"Deletion requested: {cert['requested_at']}\n"
        f"Deleted: {cert['purged_at']}\n"
        f"Rows deleted:\n{rows}\n\n"
        "Backups that still hold it expire within 35 days.\n\n"
        f"Certificate (JSON): {json.dumps(cert, sort_keys=True, separators=(',', ':'), default=str)}\n"
        f"Ed25519 signature: {signature}\n"
    )
    return {"to": to, "subject": subject, "text": text, "html": None}


def purge_workspace(conn: psycopg.Connection, tenant_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    """Delete everything that belongs to one workspace. Returns the signed certificate."""
    with conn.transaction():
        tenant = conn.execute(
            "SELECT name, locale, deletion_requested_at, deletion_contact FROM tenants"
            " WHERE id = %s FOR UPDATE",
            (tenant_id,),
        ).fetchone()
        if tenant is None:
            raise LookupError(tenant_id)
        name, locale, requested_at, contact = tenant
        _bind(conn, tenant_id)
        counts: dict[str, int] = {}
        for table in _tenant_tables():
            result = conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))  # noqa: S608
            counts[table] = result.rowcount
        # Staff accounts without email exist only for this workspace.
        managed = [
            r[0] for r in conn.execute("SELECT id FROM users WHERE managed_tenant_id = %s", (tenant_id,))
        ]
        sessions = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM auth_sessions WHERE user_id = ANY(%s) OR tenant_id = %s", (managed, tenant_id)
            )
        ]
        for table in SESSION_CHILDREN:
            conn.execute(f"DELETE FROM {table} WHERE session_id = ANY(%s)", (sessions,))  # noqa: S608
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ANY(%s)", (managed,))
        # Other people keep their accounts; their sessions just no longer point here.
        conn.execute(
            "UPDATE auth_sessions SET tenant_id = NULL, revoked_at = coalesce(revoked_at, now())"
            " WHERE tenant_id = %s",
            (tenant_id,),
        )
        for table in USER_CHILDREN:
            conn.execute(f"DELETE FROM {table} WHERE user_id = ANY(%s)", (managed,))  # noqa: S608
        counts["users"] = conn.execute("DELETE FROM users WHERE id = ANY(%s)", (managed,)).rowcount
        conn.execute("DELETE FROM outbox_events WHERE tenant_id = %s AND dispatched_at IS NULL", (tenant_id,))
        conn.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        cert = {
            "workspace_id": str(tenant_id),
            "name": name,
            "requested_at": requested_at.isoformat() if requested_at else None,
            "purged_at": now.isoformat(),
            "rows": counts,
            "digest": hashlib.sha256(json.dumps(counts, sort_keys=True).encode()).hexdigest(),
        }
        signature = sign(cert)
        if contact:
            conn.execute(
                "INSERT INTO outbox_events (id, tenant_id, topic, payload, attempts)"
                " VALUES (%s, NULL, %s, %s, 0)",
                (uuid7(), "email.send", Jsonb(_certificate_mail(cert, signature, contact, locale or "en"))),
            )
    log.info("purged workspace", extra={"tenant_id": str(tenant_id), "rows": sum(counts.values())})
    return {**cert, "signature": signature}


def purge_deleted_workspaces(conn: psycopg.Connection, now: datetime) -> list[dict[str, Any]]:
    due = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM tenants WHERE status = 'deleting' AND deletion_requested_at <= %s",
            (now - DELETION_GRACE,),
        )
    ]
    return [purge_workspace(conn, tenant_id, now) for tenant_id in due]


def _retention_days(conn: psycopg.Connection, now: datetime) -> int | None:
    """The bound workspace's audit retention under its current plan (the trial plan while
    a trial runs, as everywhere else). None keeps everything."""
    row = conn.execute(
        """
        SELECT p.audit_retention_days FROM subscriptions s
        JOIN plans p ON p.key = CASE
            WHEN s.status = 'trialing' AND s.trial_plan_key IS NOT NULL AND s.trial_ends_at > %s
            THEN s.trial_plan_key ELSE s.plan_key END
        """,
        (now,),
    ).fetchone()
    return None if row is None else row[0]


def apply_audit_retention(conn: psycopg.Connection, now: datetime) -> dict[str, int]:
    """Delete audit entries older than each workspace's plan allows, keeping an anchor."""
    purged: dict[str, int] = {}
    for (tenant_id,) in conn.execute("SELECT id FROM tenants WHERE status = 'active'").fetchall():
        with conn.transaction():
            _bind(conn, tenant_id)
            days = _retention_days(conn, now)
            if days is None:
                continue
            last = conn.execute(
                "SELECT seq, hash FROM audit_events WHERE tenant_id = %s AND occurred_at < %s"
                " ORDER BY seq DESC LIMIT 1",
                (tenant_id, now - timedelta(days=days)),
            ).fetchone()
            if last is None:
                continue
            seq, digest = last
            count = conn.execute(
                "DELETE FROM audit_events WHERE tenant_id = %s AND seq <= %s", (tenant_id, seq)
            ).rowcount
            conn.execute(
                "INSERT INTO audit_anchors (id, tenant_id, seq, hash, purged_rows, purged_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uuid7(), tenant_id, seq, digest, count, now),
            )
            purged[str(tenant_id)] = count
    return purged


def run(dsn: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    with psycopg.connect(dsn, autocommit=True) as conn:
        return {
            "workspaces_purged": len(purge_deleted_workspaces(conn, now)),
            "audit_rows_purged": sum(apply_audit_retention(conn, now).values()),
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    dsn = (
        get_settings()
        .migrations_database_url.get_secret_value()
        .replace("postgresql+psycopg://", "postgresql://")
    )
    print(json.dumps(run(dsn)))


if __name__ == "__main__":
    main()
