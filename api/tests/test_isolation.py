"""Proof that one workspace can never read or change another's data.

Three layers are tested:
1. Schema: every table with tenant_id has forced row-level security and a policy, and the
   app's database role can't bypass it.
2. Database: with tenant A bound, the app role sees none of tenant B's rows, can't write
   rows for B, and sees nothing at all with no tenant bound.
3. API: every route with an id in its path is called by workspace B's owner (who holds every
   permission) with workspace A's ids, and must answer 404 or 422 without changing anything.
   New routes are picked up automatically; an id type the test doesn't know fails the test.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import httpx
import psycopg
import pytest

from app.core.config import get_settings
from app.main import api_routes
from app.models_registry import metadata
from tests.helpers import Account, add_staff, if_match, invite_and_join, role_id, signup

# Global tables, each with the reason it has no tenant_id.
GLOBAL_TABLES = {
    "tenants": "the workspaces themselves",
    "plans": "the public price list",
    "users": "people can belong to several workspaces",
    "auth_sessions": "per user, looked up by session id from a signed token",
    "refresh_tokens": "per session, looked up by the hash of a secret",
    "auth_challenges": "per user, looked up by the hash of a secret",
    "recovery_codes": "per user",
    "email_tokens": "per user, looked up by the hash of a secret",
    "auth_events": "per user security history",
    "outbox_events": "read across tenants by the delivery job only",
    "rate_limits": "counters keyed by IP or account",
}


def app_dsn() -> str:
    return get_settings().database_url.get_secret_value().replace("postgresql+psycopg://", "postgresql://")


def test_every_tenant_table_is_protected(owner_sql: psycopg.Connection) -> None:
    tenant_tables = {
        name
        for name, table in metadata.tables.items()
        if "tenant_id" in table.c and name not in GLOBAL_TABLES
    }
    unexplained = set(metadata.tables) - tenant_tables - set(GLOBAL_TABLES)
    assert not unexplained, f"Tables without tenant_id and no reason given: {unexplained}"
    rows = owner_sql.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               EXISTS (SELECT 1 FROM pg_policies p WHERE p.tablename = c.relname
                       AND p.policyname = 'tenant_isolation')
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        """
    ).fetchall()
    state = {r[0]: r[1:] for r in rows}
    for table in tenant_tables:
        assert state[table] == (True, True, True), f"{table} is missing forced RLS or its policy"


def test_app_role_cannot_bypass_rls(owner_sql: psycopg.Connection) -> None:
    role = get_settings().app_db_role
    bypass, superuser = owner_sql.execute(
        "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = %s", (role,)
    ).fetchone() or (None, None)
    assert bypass is False
    assert superuser is False
    owned = owner_sql.execute(
        "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' AND tableowner = %s", (role,)
    ).fetchone()
    assert owned == (0,)


async def _two_workspaces(client: httpx.AsyncClient) -> tuple[Account, Account]:
    a = await signup(client, business="Alpha Traders")
    b = await signup(client, business="Beta Foods")
    return a, b


async def test_database_level_isolation(client: httpx.AsyncClient) -> None:
    a, b = await _two_workspaces(client)
    with psycopg.connect(app_dsn()) as conn:
        # Bound to A: only A's rows.
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (a.tenant_id,))
        for table in ("roles", "memberships", "employees", "branches", "subscriptions", "audit_events"):
            tenants = {r[0] for r in conn.execute(f"SELECT DISTINCT tenant_id::text FROM {table}")}  # noqa: S608
            assert tenants == {a.tenant_id}, table
        # Can't write a row for B, and can't move a row into B.
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO branches (id, tenant_id, name, timezone, is_active, version) "
                "VALUES (gen_random_uuid(), %s, 'Sneaky', 'UTC', true, 1)",
                (b.tenant_id,),
            )
        conn.rollback()
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (a.tenant_id,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE branches SET tenant_id = %s", (b.tenant_id,))
        conn.rollback()
        # Updates and deletes aimed at B's rows touch nothing.
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (a.tenant_id,))
        updated = conn.execute("UPDATE employees SET full_name = 'x' WHERE tenant_id = %s", (b.tenant_id,))
        assert updated.rowcount == 0
        conn.rollback()
        # No tenant bound: nothing at all.
        conn.execute("SELECT set_config('app.tenant_id', '', false)")
        for table in ("roles", "memberships", "employees", "branches", "audit_events"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,), table  # noqa: S608


@pytest.mark.parametrize(("table", "column"), [("audit_events", "action"), ("domain_events", "name")])
def test_logs_are_append_only_for_the_app(owner_sql: psycopg.Connection, table: str, column: str) -> None:
    with psycopg.connect(app_dsn()) as conn:
        for statement in (
            f"UPDATE {table} SET {column} = 'x'",  # noqa: S608
            f"DELETE FROM {table}",  # noqa: S608
            f"TRUNCATE {table}",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
            conn.rollback()


async def _resources(owner: Account) -> dict[str, str]:
    """Create one of everything in a workspace and return ids by path-parameter name."""
    ids: dict[str, str] = {}
    dept = await owner.post("/v1/departments", json={"name": "Kitchen"})
    ids["department_id"] = dept.json()["id"]
    person = await owner.post(
        "/v1/people", json={"full_name": "Jamal", "department_id": ids["department_id"]}
    )
    ids["employee_id"] = person.json()["id"]
    branch = await owner.post("/v1/branches", json={"name": "Second shop"})
    ids["branch_id"] = branch.json()["id"]
    role = await owner.post("/v1/roles", json={"name": "Shift lead", "permissions": ["people.view"]})
    ids["role_id"] = role.json()["id"]
    staff, staff_account = await add_staff(owner, name="Nadia")
    ids["member_id"] = staff["member"]["id"]
    member = await invite_and_join(owner)
    invite = await owner.post(
        "/v1/invites", json={"email": "later@example.com", "role_id": await role_id(owner, "employee")}
    )
    ids["invite_id"] = invite.json()["id"]
    start = datetime.now(UTC) - timedelta(hours=5)
    record = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": ids["employee_id"],
            "clock_in_at": start.isoformat(),
            "clock_out_at": (start + timedelta(hours=2)).isoformat(),
        },
    )
    ids["record_id"] = record.json()["id"]
    await member.post("/v1/attendance/clock-in", json={})
    await member.post("/v1/attendance/clock-out", json={})
    mine = (await member.get("/v1/attendance/records")).json()["items"][0]
    correction = await member.post(
        "/v1/attendance/corrections",
        json={
            "kind": "change",
            "record_id": mine["id"],
            "clock_in_at": (start - timedelta(hours=1)).isoformat(),
            "clock_out_at": start.isoformat(),
            "reason": "Forgot to clock in",
        },
    )
    ids["correction_id"] = correction.json()["id"]
    kinds = (await owner.get("/v1/leave/types")).json()
    ids["leave_type_id"] = kinds[0]["id"]
    holiday = await owner.post(
        "/v1/leave/holidays", json={"day": f"{start.year}-12-16", "name": "Victory Day"}
    )
    ids["holiday_id"] = holiday.json()["id"]
    day = (start + timedelta(days=10)).date()
    day += timedelta(days=1 if day.isoweekday() == 5 else 0)
    leave = await member.post(
        "/v1/leave/requests",
        json={"leave_type_id": ids["leave_type_id"], "start_date": str(day), "end_date": str(day)},
    )
    ids["request_id"] = leave.json()["id"]
    ids["kind"], ids["item_id"] = "leave", ids["request_id"]
    ids["notification_id"] = (await owner.get("/v1/notifications")).json()["items"][0]["id"]
    modules = ["attendance", "leave", "payroll", "tasks", "announcements", "documents"]
    await owner.put("/v1/workspace/modules", json={"modules": modules})
    project = await owner.post("/v1/projects", json={"name": "Menu", "member_ids": [ids["employee_id"]]})
    ids["project_id"] = project.json()["id"]
    task = await owner.post(
        "/v1/tasks", json={"title": "Prices", "project_id": ids["project_id"], "checklist": ["Check"]}
    )
    ids["task_id"] = task.json()["id"]
    ids["item_id"] = task.json()["checklist"][0]["id"]
    comment = await owner.post(f"/v1/tasks/{ids['task_id']}/comments", json={"body": "Hi"})
    ids["comment_id"] = comment.json()["id"]
    news = await owner.post("/v1/announcements", json={"title": "Hello", "body": "Welcome."})
    ids["announcement_id"] = news.json()["id"]
    doc = await owner.post("/v1/documents", json={"title": "Handbook", "requires_ack": True})
    ids["document_id"] = doc.json()["id"]
    version = await owner.post(
        f"/v1/documents/{ids['document_id']}/versions",
        params={"filename": "handbook.pdf"},
        content=b"%PDF-1.7",
        headers={"content-type": "application/octet-stream"},
    )
    ids["version_id"] = version.json()["current"]["id"]
    salary = await owner.post(
        "/v1/payroll/salaries",
        json={"employee_id": ids["employee_id"], "effective_from": "2024-01-01", "basic": 1_000_000},
    )
    assert salary.status_code == 201, salary.text
    loan = await owner.post(
        "/v1/payroll/loans",
        json={
            "employee_id": ids["employee_id"],
            "label": "Advance",
            "principal": 100_000,
            "installment": 50_000,
            "start_period": "2026-01",
        },
    )
    ids["loan_id"] = loan.json()["id"]
    first = start.date().replace(day=1) - timedelta(days=1)
    run = (await owner.post("/v1/payroll/runs", json={"period": f"{first:%Y-%m}"})).json()
    ids["run_id"] = run["id"]
    ids["payslip_id"] = run["payslips"][0]["id"]
    item = await owner.post(
        f"/v1/payroll/runs/{run['id']}/items",
        json={"employee_id": ids["employee_id"], "kind": "earning", "label": "Bonus", "amount": 100},
    )
    ids["item_id"] = item.json()["id"]
    sessions = (await staff_account.get("/v1/auth/sessions")).json()
    ids["session_id"] = sessions[0]["id"]
    assert all(ids.values()), ids
    return ids


def _routes() -> list[tuple[str, str, list[str]]]:
    found = []
    for route in api_routes():
        params = re.findall(r"{(\w+)}", route.path)
        if params:
            found.extend((method, route.path, params) for method in route.methods - {"HEAD", "OPTIONS"})
    return found


async def test_api_never_crosses_workspaces(client: httpx.AsyncClient) -> None:
    a, b = await _two_workspaces(client)
    ids = await _resources(a)
    routes = _routes()
    assert len(routes) >= 15
    for method, path, params in routes:
        unknown = [p for p in params if p not in ids]
        assert not unknown, f"{method} {path}: add {unknown} to the isolation test"
        url = path
        for p in params:
            url = url.replace("{" + p + "}", ids[p])
        body = {} if method in ("POST", "PATCH", "PUT") else None
        headers = {**b.headers, **if_match(1)}
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code in (404, 422), f"{method} {path} answered {response.status_code}"

    # And A's data is untouched.
    person = await a.get(f"/v1/people/{ids['employee_id']}")
    assert person.json()["full_name"] == "Jamal"
    members = (await a.get("/v1/members")).json()["items"]
    assert any(m["id"] == ids["member_id"] and m["status"] == "active" for m in members)


async def test_lists_only_show_own_workspace(client: httpx.AsyncClient) -> None:
    a, b = await _two_workspaces(client)
    await _resources(a)
    for url in ("/v1/people", "/v1/members", "/v1/audit", "/v1/attendance/records"):
        items = (await b.get(url)).json()["items"]
        names = {str(i.get("full_name") or i.get("name") or i.get("employee_name") or "") for i in items}
        assert "Jamal" not in names, url
        assert "Nadia" not in names, url
    for url in ("/v1/departments", "/v1/roles", "/v1/branches", "/v1/invites", "/v1/attendance/present"):
        body = (await b.get(url)).json()
        text = str(body)
        assert "Kitchen" not in text
        assert "Shift lead" not in text
        assert "Second shop" not in text
        assert "later@example.com" not in text


async def test_token_for_one_workspace_cant_be_pointed_at_another(client: httpx.AsyncClient) -> None:
    a, b = await _two_workspaces(client)
    switch = await a.post("/v1/auth/switch", json={"tenant_id": b.tenant_id})
    assert switch.status_code == 403
    # Invite tokens carry their workspace; tampering with it finds nothing.
    await invite_and_join(a)
    forged = await client.get("/v1/invites/lookup", params={"token": f"{b.tenant_id}.not-a-real-secret"})
    assert forged.status_code == 422
