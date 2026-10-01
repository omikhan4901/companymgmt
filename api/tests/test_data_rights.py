"""Data rights: the admin two-step policy, deleting and restoring a workspace, the purge
after the grace period (with a signed certificate), and audit retention."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import httpx
import psycopg
import pyotp

from app.core.security.tokens import _keys
from app.jobs import maintenance
from tests.conftest import owner_dsn
from tests.helpers import Account, add_staff, invite_and_join, signup


async def enable_mfa(account: Account) -> None:
    secret = (await account.post("/v1/auth/mfa/setup")).json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert (await account.post("/v1/auth/mfa/enable", json={"code": code})).status_code == 200


# ---- Two-step verification for admins ---------------------------------------------------


async def test_admins_can_be_required_to_use_two_step(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    admin = await invite_and_join(owner, role="admin")
    _, staff = await add_staff(owner)
    # The owner can't switch it on without using it themselves.
    refused = await owner.patch("/v1/workspace", json={"require_admin_mfa": True})
    assert refused.json()["code"] == "mfa_required_first"
    await enable_mfa(owner)
    on = await owner.patch("/v1/workspace", json={"require_admin_mfa": True})
    assert on.status_code == 200, on.text
    assert on.json()["require_admin_mfa"] is True

    blocked = await admin.get("/v1/members")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "mfa_setup_required"
    me = (await admin.get("/v1/auth/me")).json()["workspace"]
    assert (me["require_admin_mfa"], me["mfa_setup_required"]) == (True, True)
    # Staff aren't affected; the admin is let back in once two-step is on.
    assert (await staff.get("/v1/attendance/status")).status_code == 200
    await enable_mfa(admin)
    assert (await admin.get("/v1/members")).status_code == 200
    assert (await admin.get("/v1/auth/me")).json()["workspace"]["mfa_setup_required"] is False


# ---- Deleting and restoring --------------------------------------------------------------


async def test_owner_deletes_and_restores_a_workspace(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client, business="Cha Ghor")
    admin = await invite_and_join(owner, role="admin")
    # Only the owner, with the name typed again, after confirming who they are.
    assert (await admin.post("/v1/workspace/delete", json={"confirm_name": "Cha Ghor"})).status_code == 403
    wrong = await owner.post("/v1/workspace/delete", json={"confirm_name": "Cha"})
    assert wrong.status_code == 422
    owner_sql.execute("UPDATE auth_sessions SET reauth_at = now() - interval '1 hour'")
    stale = await owner.post("/v1/workspace/delete", json={"confirm_name": "cha ghor"})
    assert stale.json()["code"] == "reauth_required"
    assert (await owner.post("/v1/auth/reauth", json={"password": owner.password})).status_code == 204
    deleted = await owner.post("/v1/workspace/delete", json={"confirm_name": "cha ghor"})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleting"

    # Nobody can use it now; the answer says when it goes for good.
    gone = await admin.get("/v1/members")
    assert gone.status_code == 410
    assert gone.json()["code"] == "workspace_deleted"
    assert "purge_after" in gone.json()
    assert (await admin.post("/v1/workspace/restore")).status_code == 403
    restored = await owner.post("/v1/workspace/restore")
    assert restored.status_code == 200, restored.text
    assert (await admin.get("/v1/members")).status_code == 200
    assert (await owner.post("/v1/workspace/restore")).json()["code"] == "not_deleting"
    actions = [e["action"] for e in (await owner.get("/v1/audit")).json()["items"]]
    assert {"workspace.deletion_requested", "workspace.restored"} <= set(actions)


async def test_purge_after_the_grace_period(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client, business="Gone Soon")
    _, staff = await add_staff(owner, name="Temp")
    other = await signup(client, business="Stays")
    await owner.post("/v1/people", json={"full_name": "Someone"})
    tenant_id = owner.tenant_id
    staff_user = staff.me["id"]
    assert (await owner.post("/v1/workspace/delete", json={"confirm_name": "Gone Soon"})).status_code == 200

    # Within the grace period nothing is purged.
    soon = maintenance.run(owner_dsn(), now=datetime.now(UTC) + timedelta(days=29))
    assert soon["workspaces_purged"] == 0
    later = datetime.now(UTC) + timedelta(days=31)
    assert maintenance.run(owner_dsn(), now=later)["workspaces_purged"] == 1

    assert owner_sql.execute("SELECT count(*) FROM tenants WHERE id = %s", (tenant_id,)).fetchone() == (0,)
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))
    for table in ("employees", "memberships", "roles", "branches", "audit_events", "subscriptions"):
        count = owner_sql.execute(f"SELECT count(*) FROM {table} WHERE tenant_id = %s", (tenant_id,))  # noqa: S608
        assert count.fetchone() == (0,), table
    # Staff accounts without email go with it; the owner keeps their account.
    assert owner_sql.execute("SELECT count(*) FROM users WHERE id = %s", (staff_user,)).fetchone() == (0,)
    assert owner_sql.execute("SELECT count(*) FROM users WHERE id = %s", (owner.me["id"],)).fetchone() == (1,)
    # Another workspace is untouched.
    assert (await other.get("/v1/members")).status_code == 200

    # A signed certificate is on its way to the owner.
    row = owner_sql.execute(
        "SELECT payload FROM outbox_events"
        " WHERE payload->>'to' = %s AND payload->>'subject' LIKE 'Deletion certificate%%'",
        (owner.email,),
    ).fetchone()
    assert row is not None
    text = row[0]["text"]
    cert = json.loads(text.split("Certificate (JSON): ")[1].split("\n")[0])
    signature = text.split("Ed25519 signature: ")[1].strip()
    assert cert["workspace_id"] == tenant_id
    assert cert["rows"]["employees"] == 3
    _, public = _keys()
    body = json.dumps(cert, sort_keys=True, separators=(",", ":"), default=str).encode()
    public.verify(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)), body)


# ---- Audit retention ---------------------------------------------------------------------


async def test_audit_retention_keeps_the_chain_verifiable(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    for name in ("Kitchen", "Delivery", "Front"):
        await owner.post("/v1/departments", json={"name": name})
    before = (await owner.get("/v1/audit")).json()["items"]
    # Off the trial, the Free plan keeps 30 days; a month later the old entries go.
    owner_sql.execute(
        "UPDATE subscriptions SET status = 'active', trial_plan_key = NULL WHERE tenant_id = %s",
        (owner.tenant_id,),
    )
    far = datetime.now(UTC) + timedelta(days=31)
    purged = maintenance.apply_audit_retention(psycopg.connect(owner_dsn(), autocommit=True), far)
    assert purged[owner.tenant_id] == len(before)
    await owner.post("/v1/departments", json={"name": "Later"})
    check = await owner.get("/v1/audit/verify")
    assert check.status_code == 200, check.text
    assert check.json()["ok"] is True
    # Removing the anchor breaks verification (the start of the chain can't be proven).
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    owner_sql.execute("DELETE FROM audit_anchors WHERE tenant_id = %s", (owner.tenant_id,))
    assert (await owner.get("/v1/audit/verify")).json()["ok"] is False


# ---- Exports -----------------------------------------------------------------------------


async def test_owner_exports_the_whole_workspace(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    admin = await invite_and_join(owner, role="admin")
    person = (
        await owner.post("/v1/people", json={"full_name": "=HYPERLINK(evil)", "national_id": "1990123456789"})
    ).json()
    await owner.post(
        "/v1/payroll/salaries",
        json={
            "employee_id": person["id"],
            "effective_from": "2024-01-01",
            "basic": 1_000_000,
            "payment_method": "bank",
            "provider": "City Bank",
            "account": "1234567890",
        },
    )
    assert (await admin.get("/v1/privacy/workspace-export")).status_code == 403
    owner_sql.execute("UPDATE auth_sessions SET reauth_at = now() - interval '1 hour'")
    assert (await owner.get("/v1/privacy/workspace-export")).json()["code"] == "reauth_required"
    await owner.post("/v1/auth/reauth", json={"password": owner.password})

    response = await owner.get("/v1/privacy/workspace-export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {
        "README.txt",
        "manifest.json",
        "data/employees.json",
        "data/users.json",
        "csv/people.csv",
    } <= names
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["format"] == "companymgmt-export"
    assert manifest["tables"]["employees"] == 3
    employees = json.loads(archive.read("data/employees.json"))
    exported = next(e for e in employees if e["id"] == person["id"])
    assert exported["national_id"] == "1990123456789"
    assert "national_id_enc" not in exported
    salaries = json.loads(archive.read("data/salary_structures.json"))
    assert salaries[0]["account"] == "1234567890"
    # Cells that look like formulas are neutralised in the spreadsheets.
    assert "'=HYPERLINK(evil)" in archive.read("csv/people.csv").decode("utf-8-sig")
    # Only this workspace.
    assert all(r["tenant_id"] == owner.tenant_id for r in employees)
    audit_items = (await owner.get("/v1/audit", params={"action": "workspace.exported"})).json()["items"]
    assert audit_items


async def test_people_export_their_own_data(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Nadia")
    _, other = await add_staff(owner, name="Other")
    await staff.post("/v1/attendance/clock-in", json={})
    await other.post("/v1/attendance/clock-in", json={})
    response = await staff.get("/v1/privacy/my-data")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["account"]["name"] == "Nadia"
    assert data["profile"]["full_name"] == "Nadia"
    assert len(data["attendance"]) == 1
    assert data["attendance"][0]["employee_id"] == data["profile"]["id"]
    assert "Other" not in json.dumps(data)
    assert data["payslips"] == []
