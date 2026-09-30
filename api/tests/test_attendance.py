"""Attendance: clocking, time zones, corrections, manual records, timesheets, export."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import psycopg

from tests.helpers import Account, add_staff, if_match, invite_and_join, signup


def iso(value: datetime) -> str:
    return value.isoformat()


async def employee_id(account: Account) -> str:
    return str((await account.get("/v1/people/me")).json()["id"])


def shift_clock_in(sql: psycopg.Connection, account: Account, hours_ago: float) -> None:
    sql.execute("SELECT set_config('app.tenant_id', %s, false)", (account.tenant_id,))
    sql.execute(
        "UPDATE attendance_records SET clock_in_at = now() - make_interval(secs => %s) "
        "WHERE clock_out_at IS NULL",
        (hours_ago * 3600,),
    )


async def test_clock_in_and_out(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    status = (await owner.get("/v1/attendance/status")).json()
    assert status["open_record"] is None
    started = await owner.post(
        "/v1/attendance/clock-in", json={"note": "Opening", "client_time": iso(datetime.now(UTC))}
    )
    assert started.status_code == 201
    record = started.json()
    assert record["status"] == "open"
    assert record["branch_id"]
    again = await owner.post("/v1/attendance/clock-in", json={})
    assert again.status_code == 409
    assert again.json()["code"] == "already_clocked_in"
    assert again.json()["record"]["id"] == record["id"]
    done = await owner.post("/v1/attendance/clock-out", json={"note": "Closing"})
    assert done.status_code == 200
    assert done.json()["status"] == "closed"
    assert done.json()["minutes"] == 0
    assert done.json()["note"] == "Opening · Closing"
    assert (await owner.post("/v1/attendance/clock-out", json={})).json()["code"] == "not_clocked_in"


async def test_double_click_clock_in_creates_one_record(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    results = await asyncio.gather(*(owner.post("/v1/attendance/clock-in", json={}) for _ in range(5)))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409, 409]
    records = (await owner.get("/v1/attendance/records")).json()["items"]
    assert len(records) == 1


async def test_overnight_shift_belongs_to_the_day_it_started(client: httpx.AsyncClient) -> None:
    owner = await signup(client, timezone="Asia/Dhaka")
    me = await employee_id(owner)
    # 22:00 to 06:00 Dhaka time (UTC+6).
    start = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    response = await owner.post(
        "/v1/attendance/records",
        json={"employee_id": me, "clock_in_at": iso(start), "clock_out_at": iso(start + timedelta(hours=8))},
    )
    assert response.status_code == 201
    assert response.json()["business_date"] == "2026-03-10"
    assert response.json()["minutes"] == 480
    # 01:30 local on 2 May is still 1 May in UTC; the local day wins.
    early = datetime(2026, 5, 1, 19, 30, tzinfo=UTC)
    second = await owner.post(
        "/v1/attendance/records",
        json={"employee_id": me, "clock_in_at": iso(early), "clock_out_at": iso(early + timedelta(hours=1))},
    )
    assert second.json()["business_date"] == "2026-05-02"


async def test_hours_across_daylight_saving_change(client: httpx.AsyncClient) -> None:
    owner = await signup(client, timezone="Europe/London", country="GB")
    me = await employee_id(owner)
    # Clocks go forward at 01:00 UTC on 29 March 2026: 00:30-03:30 UTC is 3 real hours,
    # though the wall clock shows 00:30-04:30.
    start = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    response = await owner.post(
        "/v1/attendance/records",
        json={"employee_id": me, "clock_in_at": iso(start), "clock_out_at": iso(start + timedelta(hours=3))},
    )
    assert response.json()["minutes"] == 180
    leap = datetime(2024, 2, 29, 9, 0, tzinfo=UTC)
    leap_day = await owner.post(
        "/v1/attendance/records",
        json={"employee_id": me, "clock_in_at": iso(leap), "clock_out_at": iso(leap + timedelta(hours=9))},
    )
    assert leap_day.json()["business_date"] == "2024-02-29"


async def test_manual_record_validation(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    now = datetime.now(UTC)
    cases = [
        {"clock_in_at": iso(now + timedelta(hours=1))},
        {"clock_in_at": iso(now - timedelta(hours=2)), "clock_out_at": iso(now - timedelta(hours=3))},
        {"clock_in_at": iso(now - timedelta(hours=30)), "clock_out_at": iso(now - timedelta(hours=2))},
        {"clock_in_at": iso(now - timedelta(hours=2)), "clock_out_at": iso(now + timedelta(hours=2))},
        {"clock_in_at": "2026-03-10T10:00:00"},
        {"clock_in_at": "yesterday"},
    ]
    for case in cases:
        response = await owner.post("/v1/attendance/records", json={"employee_id": me, **case})
        assert response.status_code == 422, case
    ok = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": me,
            "clock_in_at": iso(now - timedelta(hours=5)),
            "clock_out_at": iso(now - timedelta(hours=3)),
        },
    )
    assert ok.status_code == 201
    overlap = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": me,
            "clock_in_at": iso(now - timedelta(hours=4)),
            "clock_out_at": iso(now - timedelta(hours=2)),
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "overlap"
    # Back to back is fine.
    touching = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": me,
            "clock_in_at": iso(now - timedelta(hours=3)),
            "clock_out_at": iso(now - timedelta(hours=2)),
        },
    )
    assert touching.status_code == 201


async def test_edit_and_delete_records_are_audited(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    start = datetime.now(UTC) - timedelta(hours=6)
    record = (
        await owner.post(
            "/v1/attendance/records",
            json={
                "employee_id": me,
                "clock_in_at": iso(start),
                "clock_out_at": iso(start + timedelta(hours=1)),
            },
        )
    ).json()
    url = f"/v1/attendance/records/{record['id']}"
    edited = await owner.patch(
        url, json={"clock_out_at": iso(start + timedelta(hours=2))}, headers=if_match(record["version"])
    )
    assert edited.json()["minutes"] == 120
    stale = await owner.patch(url, json={"note": "x"}, headers=if_match(record["version"]))
    assert stale.status_code == 412
    assert (await owner.delete(url)).status_code == 204
    actions = [
        e["action"] for e in (await owner.get("/v1/audit", params={"action": "attendance."})).json()["items"]
    ]
    assert actions == ["attendance.record_deleted", "attendance.record_edited", "attendance.record_added"]


async def test_forgot_to_clock_out_flow(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    await staff.post("/v1/attendance/clock-in", json={})
    shift_clock_in(owner_sql, owner, 30)
    status = (await staff.get("/v1/attendance/status")).json()
    assert status["forgot_clock_out"] is True
    blocked = await staff.post("/v1/attendance/clock-out", json={})
    assert blocked.json()["code"] == "forgot_clock_out"
    record_id = blocked.json()["record"]["id"]
    clock_in = datetime.fromisoformat(status["open_record"]["clock_in_at"])
    request = await staff.post(
        "/v1/attendance/corrections",
        json={
            "kind": "change",
            "record_id": record_id,
            "clock_in_at": iso(clock_in),
            "clock_out_at": iso(clock_in + timedelta(hours=8)),
            "reason": "Left at the usual time",
        },
    )
    assert request.status_code == 201, request.text
    # Set aside, not counted, and the person can clock in again.
    records = (await staff.get("/v1/attendance/records")).json()["items"]
    assert records[0]["status"] == "auto_closed"
    assert records[0]["minutes"] is None
    assert (await staff.post("/v1/attendance/clock-in", json={})).status_code == 201
    duplicate = await staff.post(
        "/v1/attendance/corrections",
        json={
            "kind": "change",
            "record_id": record_id,
            "clock_in_at": iso(clock_in),
            "clock_out_at": iso(clock_in + timedelta(hours=7)),
            "reason": "Again",
        },
    )
    assert duplicate.json()["code"] == "duplicate_request"
    pending = (await owner.get("/v1/attendance/corrections")).json()
    assert len(pending) == 1
    approved = await owner.post(f"/v1/attendance/corrections/{pending[0]['id']}/approve", json={"note": "OK"})
    assert approved.status_code == 200
    fixed = next(
        r for r in (await owner.get("/v1/attendance/records")).json()["items"] if r["id"] == record_id
    )
    assert fixed["status"] == "closed"
    assert fixed["minutes"] == 480
    again = await owner.post(f"/v1/attendance/corrections/{pending[0]['id']}/reject", json={})
    assert again.json()["code"] == "already_decided"


async def test_corrections_add_reject_cancel(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    _, staff = await add_staff(owner)
    day = datetime.now(UTC) - timedelta(days=2)
    body = {
        "kind": "add",
        "clock_in_at": iso(day),
        "clock_out_at": iso(day + timedelta(hours=4)),
        "reason": "Phone was dead",
    }
    add = await staff.post("/v1/attendance/corrections", json=body)
    assert add.status_code == 201
    assert (await staff.post("/v1/attendance/corrections", json=body)).json()["code"] == "duplicate_request"
    mine = (await staff.get("/v1/attendance/corrections", params={"mine": True})).json()
    assert [c["id"] for c in mine] == [add.json()["id"]]
    ok = await manager.post(f"/v1/attendance/corrections/{add.json()['id']}/approve", json={})
    assert ok.status_code == 200
    assert (await staff.get("/v1/attendance/records")).json()["items"][0]["source"] == "correction"
    second = await staff.post(
        "/v1/attendance/corrections",
        json={
            **body,
            "clock_in_at": iso(day - timedelta(days=1)),
            "clock_out_at": iso(day - timedelta(hours=20)),
        },
    )
    rejected = await manager.post(
        f"/v1/attendance/corrections/{second.json()['id']}/reject", json={"note": "No"}
    )
    assert rejected.json()["status"] == "rejected"
    third = await staff.post(
        "/v1/attendance/corrections",
        json={
            **body,
            "clock_in_at": iso(day - timedelta(days=3)),
            "clock_out_at": iso(day - timedelta(days=3) + timedelta(hours=1)),
        },
    )
    cancelled = await staff.post(f"/v1/attendance/corrections/{third.json()['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    assert (await staff.post(f"/v1/attendance/corrections/{third.json()['id']}/cancel")).status_code == 409
    # Employees can't approve.
    fourth = await staff.post(
        "/v1/attendance/corrections",
        json={
            **body,
            "clock_in_at": iso(day - timedelta(days=5)),
            "clock_out_at": iso(day - timedelta(days=5) + timedelta(hours=1)),
        },
    )
    assert (
        await staff.post(f"/v1/attendance/corrections/{fourth.json()['id']}/approve", json={})
    ).status_code == 403
    # Bad requests.
    no_times = await staff.post("/v1/attendance/corrections", json={"kind": "add", "reason": "hmm"})
    assert no_times.status_code == 422
    no_record = await staff.post("/v1/attendance/corrections", json={"kind": "remove", "reason": "oops"})
    assert no_record.status_code == 422


async def test_managers_cannot_approve_their_own_request(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    day = datetime.now(UTC) - timedelta(days=1)
    own = await manager.post(
        "/v1/attendance/corrections",
        json={
            "kind": "add",
            "clock_in_at": iso(day),
            "clock_out_at": iso(day + timedelta(hours=2)),
            "reason": "Forgot",
        },
    )
    response = await manager.post(f"/v1/attendance/corrections/{own.json()['id']}/approve", json={})
    assert response.json()["code"] == "self_approval"


async def test_removing_a_member_closes_their_shift(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    data, staff = await add_staff(owner)
    await staff.post("/v1/attendance/clock-in", json={})
    assert (await owner.delete(f"/v1/members/{data['member']['id']}")).status_code == 204
    records = (await owner.get("/v1/attendance/records")).json()["items"]
    assert records[0]["status"] == "auto_closed"
    assert (await owner.get("/v1/attendance/present")).json() == []


async def test_scope_limits_what_managers_see(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    kitchen = (await owner.post("/v1/departments", json={"name": "Kitchen"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    manager = await invite_and_join(owner, role="manager", scope_department_id=kitchen["id"])
    cook_data, cook = await add_staff(owner, name="Cook", scope_department_id=kitchen["id"])
    seller_data, seller = await add_staff(owner, name="Seller", scope_department_id=sales["id"])
    await cook.post("/v1/attendance/clock-in", json={})
    await seller.post("/v1/attendance/clock-in", json={})
    present = {p["employee_name"] for p in (await manager.get("/v1/attendance/present")).json()}
    assert present == {"Cook"}
    names = {r["employee_name"] for r in (await manager.get("/v1/attendance/records")).json()["items"]}
    assert names == {"Cook"}
    await seller.post("/v1/attendance/clock-out", json={})
    records = (await seller.get("/v1/attendance/records")).json()["items"]
    day = datetime.now(UTC) - timedelta(days=1)
    request = await seller.post(
        "/v1/attendance/corrections",
        json={
            "kind": "change",
            "record_id": records[0]["id"],
            "clock_in_at": iso(day),
            "clock_out_at": iso(day + timedelta(hours=1)),
            "reason": "Wrong",
        },
    )
    outside = await manager.post(f"/v1/attendance/corrections/{request.json()['id']}/approve", json={})
    assert outside.status_code == 404
    assert (await manager.get("/v1/attendance/corrections")).json() == []
    assert cook_data
    assert seller_data


async def test_employees_only_see_their_own_records(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    await owner.post("/v1/attendance/clock-in", json={})
    _, staff = await add_staff(owner)
    await staff.post("/v1/attendance/clock-in", json={})
    mine = (await staff.get("/v1/attendance/records")).json()["items"]
    assert len(mine) == 1
    other = await employee_id(owner)
    assert (await staff.get("/v1/attendance/records", params={"employee_id": other})).status_code == 404
    assert (await staff.get("/v1/attendance/present")).status_code == 403
    assert (
        await staff.get("/v1/attendance/export.csv", params={"from": "2026-01-01", "to": "2026-01-02"})
    ).status_code == 403
    sheet = (await staff.get("/v1/attendance/timesheet", params={"month": "2026-09"})).json()
    assert len(sheet["rows"]) == 1


async def test_timesheet_totals(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    base = datetime(2026, 2, 27, 3, 0, tzinfo=UTC)  # 09:00 Dhaka
    for day, hours in ((0, 8), (0, 1), (1, 4)):
        start = base + timedelta(days=day, hours=9 if hours == 1 else 0)
        await owner.post(
            "/v1/attendance/records",
            json={
                "employee_id": me,
                "clock_in_at": iso(start),
                "clock_out_at": iso(start + timedelta(hours=hours)),
            },
        )
    sheet = (await owner.get("/v1/attendance/timesheet", params={"month": "2026-02"})).json()
    assert sheet["end"] == "2026-02-28"
    row = next(r for r in sheet["rows"] if r["employee_id"] == me)
    assert row["total_minutes"] == 13 * 60
    assert row["days_present"] == 2
    assert [d["records"] for d in row["days"]] == [2, 1]
    assert (await owner.get("/v1/attendance/timesheet", params={"month": "2026-13"})).status_code == 422
    assert (await owner.get("/v1/attendance/timesheet", params={"month": "26-1"})).status_code == 422


async def test_csv_export_is_safe(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    person = (await owner.post("/v1/people", json={"full_name": '=HYPERLINK("http://evil")'})).json()
    bangla = (await owner.post("/v1/people", json={"full_name": "মোঃ করিম"})).json()
    start = datetime(2026, 1, 5, 4, 0, tzinfo=UTC)
    for p in (person, bangla):
        await owner.post(
            "/v1/attendance/records",
            json={
                "employee_id": p["id"],
                "clock_in_at": iso(start),
                "clock_out_at": iso(start + timedelta(hours=2)),
                "note": "+1 bonus",
            },
        )
    response = await owner.get("/v1/attendance/export.csv", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    assert "'=HYPERLINK" in text
    assert "'+1 bonus" in text
    assert "মোঃ করিম" in text
    too_long = await owner.get("/v1/attendance/export.csv", params={"from": "2024-01-01", "to": "2026-01-31"})
    assert too_long.status_code == 422


async def test_records_pagination_and_filters(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    me = await employee_id(owner)
    base = datetime(2026, 4, 1, 3, 0, tzinfo=UTC)
    for day in range(5):
        start = base + timedelta(days=day)
        await owner.post(
            "/v1/attendance/records",
            json={
                "employee_id": me,
                "clock_in_at": iso(start),
                "clock_out_at": iso(start + timedelta(hours=1)),
            },
        )
    page = (await owner.get("/v1/attendance/records", params={"limit": 2})).json()
    assert len(page["items"]) == 2
    rest = (
        await owner.get("/v1/attendance/records", params={"limit": 10, "cursor": page["next_cursor"]})
    ).json()
    assert len(rest["items"]) == 3
    ranged = (
        await owner.get("/v1/attendance/records", params={"from": "2026-04-02", "to": "2026-04-03"})
    ).json()
    assert [r["business_date"] for r in ranged["items"]] == ["2026-04-03", "2026-04-02"]
    bad = await owner.get("/v1/attendance/records", params={"from": "2026-04-05", "to": "2026-04-01"})
    assert bad.status_code == 422


async def test_inactive_people_cannot_clock_in(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    me = (await staff.get("/v1/people/me")).json()
    await owner.patch(f"/v1/people/{me['id']}", json={"status": "inactive"}, headers=if_match(me["version"]))
    response = await staff.post("/v1/attendance/clock-in", json={})
    assert response.json()["code"] == "no_profile"
