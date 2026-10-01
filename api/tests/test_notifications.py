"""Notifications: the right people hear about requests and decisions, and only they do."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import psycopg

from app.core.time import today
from app.jobs import maintenance
from tests.conftest import owner_dsn
from tests.helpers import Account, add_staff, invite_and_join, signup
from tests.test_payroll import employee_id, last_month, set_salary

NEXT = today("Asia/Dhaka").year + 1


async def inbox(account: Account, **params: Any) -> dict[str, Any]:
    response = await account.get("/v1/notifications", params=params)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def kinds(account: Account) -> list[str]:
    return [n["kind"] for n in (await inbox(account))["items"]]


async def ask_leave(account: Account, day: int, **extra: Any) -> dict[str, Any]:
    types = (await account.get("/v1/leave/types")).json()
    casual = next(t["id"] for t in types if t["name"] == "Casual leave")
    start = str(date(NEXT, 3, day))
    response = await account.post(
        "/v1/leave/requests",
        json={"leave_type_id": casual, "start_date": start, "end_date": start, **extra},
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_leave_requests_reach_the_approvers_in_scope(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    _, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    _, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])

    cooked = await ask_leave(cook, 3)
    await ask_leave(seller, 4)
    # The kitchen manager hears about the cook only; the owner about both.
    mine = (await inbox(manager))["items"]
    assert [(n["kind"], n["data"]["employee_name"]) for n in mine] == [("leave.requested", "Cook")]
    assert mine[0]["link"] == "/app/leave"
    assert mine[0]["actor_name"] == "Cook"
    assert {n["data"]["employee_name"] for n in (await inbox(owner))["items"]} == {"Cook", "Seller"}
    # Nobody is told about their own request.
    assert await kinds(cook) == []

    assert (await manager.post(f"/v1/leave/requests/{cooked['id']}/approve", json={})).status_code == 200
    told = (await inbox(cook))["items"]
    assert [n["kind"] for n in told] == ["leave.approved"]
    assert told[0]["actor_name"] == "Member Person"
    assert told[0]["data"]["start_date"] == f"{NEXT}-03-03"
    assert (await cook.get("/v1/notifications/unread")).json() == {"unread": 1}
    # The manager's own approval doesn't come back to them.
    assert await kinds(manager) == ["leave.requested"]


async def test_cancellations_tell_the_other_side(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    first = await ask_leave(staff, 3)
    second = await ask_leave(staff, 10)
    # The person withdraws: the approvers hear.
    assert (await staff.post(f"/v1/leave/requests/{first['id']}/cancel", json={})).status_code == 200
    assert (await kinds(owner))[0] == "leave.cancelled"
    # Someone else cancels it: the person hears.
    assert (await owner.post(f"/v1/leave/requests/{second['id']}/cancel", json={})).status_code == 200
    assert await kinds(staff) == ["leave.cancelled"]


async def test_time_fixes_go_to_approvers_and_back(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    day = datetime.now(UTC) - timedelta(days=2)
    body = {
        "kind": "add",
        "clock_in_at": day.isoformat(),
        "clock_out_at": (day + timedelta(hours=4)).isoformat(),
        "reason": "Phone was dead",
    }
    created = await staff.post("/v1/attendance/corrections", json=body)
    assert created.status_code == 201, created.text
    assert await kinds(owner) == ["attendance.correction_requested"]
    approved = await owner.post(f"/v1/attendance/corrections/{created.json()['id']}/approve", json={})
    assert approved.status_code == 200, approved.text
    told = (await inbox(staff))["items"]
    assert [n["kind"] for n in told] == ["attendance.correction_approved"]
    assert told[0]["link"] == "/app/attendance"
    # A fix the owner makes directly needs nobody's approval and tells nobody.
    owner_fix = await owner.post("/v1/attendance/corrections", json={**body, "reason": "Owner's own"})
    assert owner_fix.status_code == 201, owner_fix.text
    assert await kinds(owner) == ["attendance.correction_requested"]


async def test_payslips_ready_without_the_run_totals(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    accountant = await invite_and_join(owner, role="accountant")
    _, staff = await add_staff(owner, name="Karim")
    await set_salary(owner, await employee_id(staff))
    period = last_month()
    run = (await accountant.post("/v1/payroll/runs", json={"period": period})).json()
    assert (await accountant.post(f"/v1/payroll/runs/{run['id']}/submit")).status_code == 200
    submitted = (await inbox(owner))["items"]
    assert submitted[0]["kind"] == "payroll.submitted"
    assert submitted[0]["data"]["period"] == period
    final = await owner.post(f"/v1/payroll/runs/{run['id']}/finalize")
    assert final.status_code == 200, final.text
    told = (await inbox(staff))["items"]
    assert [n["kind"] for n in told] == ["payroll.finalized"]
    assert told[0]["data"] == {"period": period}
    # The accountant prepared it but has no payslip in it.
    assert await kinds(accountant) == []


async def test_reading_and_paging(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    types = (await staff.get("/v1/leave/types")).json()
    unpaid = next(t["id"] for t in types if t["name"] == "Unpaid leave")  # no yearly cap
    day, asked = date(NEXT, 1, 1), []
    while len(asked) < 25 and day.month < 3:  # skipping weekly offs and holidays
        body = {"leave_type_id": unpaid, "start_date": str(day), "end_date": str(day)}
        if (await staff.post("/v1/leave/requests", json=body)).status_code == 201:
            asked.append(str(day))
        day += timedelta(days=1)
    assert len(asked) == 25
    assert (await owner.get("/v1/notifications/unread")).json() == {"unread": 25}
    first = await inbox(owner)
    assert len(first["items"]) == 20
    assert first["unread"] == 25
    assert first["items"][0]["data"]["start_date"] == asked[-1]  # newest first
    rest = await inbox(owner, cursor=first["next_cursor"])
    assert len(rest["items"]) == 5
    assert rest["next_cursor"] is None
    seen = {n["id"] for n in first["items"]} | {n["id"] for n in rest["items"]}
    assert len(seen) == 25

    one = first["items"][0]["id"]
    assert (await owner.post(f"/v1/notifications/{one}/read")).status_code == 204
    assert (await owner.post(f"/v1/notifications/{one}/read")).status_code == 204
    assert (await owner.get("/v1/notifications/unread")).json() == {"unread": 24}
    assert len((await inbox(owner, unread=True, limit=100))["items"]) == 24
    # Someone else's notification is not yours to read.
    assert (await staff.post(f"/v1/notifications/{one}/read")).status_code == 404
    assert (await owner.post("/v1/notifications/read-all")).json() == {"unread": 0}
    assert (await inbox(owner, unread=True))["items"] == []


async def test_old_notifications_are_cleared(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    await ask_leave(staff, 3)
    soon = datetime.now(UTC) + timedelta(days=30)
    maintenance.apply_audit_retention(psycopg.connect(owner_dsn(), autocommit=True), soon)
    assert len((await inbox(owner))["items"]) == 1
    later = datetime.now(UTC) + timedelta(days=181)
    maintenance.apply_audit_retention(psycopg.connect(owner_dsn(), autocommit=True), later)
    assert (await inbox(owner))["items"] == []
