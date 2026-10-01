"""The overview report: numbers worked out from a week whose every detail we set."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.time import today
from tests.helpers import Account, add_staff, invite_and_join, signup

DHAKA = ZoneInfo("Asia/Dhaka")


def week() -> list[date]:
    """Monday to Sunday, two weeks ago: all in the past. Friday is the day off."""
    now = today("Asia/Dhaka")
    monday = now - timedelta(days=now.weekday() + 14)
    return [monday + timedelta(days=i) for i in range(7)]


async def shift(owner: Account, employee_id: str, day: date, at: time) -> None:
    start = datetime.combine(day, at, DHAKA)
    response = await owner.post(
        "/v1/attendance/records",
        json={
            "employee_id": employee_id,
            "clock_in_at": start.astimezone(UTC).isoformat(),
            "clock_out_at": (start + timedelta(hours=8)).astimezone(UTC).isoformat(),
        },
    )
    assert response.status_code == 201, response.text


async def report(account: Account, start: date, end: date, **extra: Any) -> httpx.Response:
    return await account.get("/v1/reports/overview", params={"from": str(start), "to": str(end), **extra})


async def setup(client: httpx.AsyncClient) -> dict[str, Any]:
    owner = await signup(client)
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    _, karim = await add_staff(owner, name="Karim", scope_department_id=design["id"])
    _, salma = await add_staff(owner, name="Salma", scope_department_id=sales["id"])
    karim_id = (await karim.get("/v1/leave/balances")).json()["employee_id"]
    salma_id = (await salma.get("/v1/leave/balances")).json()["employee_id"]
    mon, tue, wed, thu, _fri, sat, sun = week()
    # Thursday is a holiday; Friday the weekly day off: five working days.
    await owner.post("/v1/leave/holidays", json={"day": str(thu), "name": "Holiday"})
    for day in (mon, tue, wed, sat, sun):
        await shift(owner, karim_id, day, time(9, 40) if day in (tue, sat) else time(9, 0))
    for day in (tue, wed, sat):
        await shift(owner, salma_id, day, time(8, 55))
    # Salma's Monday off, approved; Sunday she just didn't come.
    kinds = {k["name"]: k["id"] for k in (await owner.get("/v1/leave/types")).json()}
    asked = await owner.post(
        "/v1/leave/requests",
        json={
            "employee_id": salma_id,
            "leave_type_id": kinds["Casual leave"],
            "start_date": str(mon),
            "end_date": str(mon),
        },
    )
    assert asked.status_code == 201, asked.text
    assert (await owner.post(f"/v1/leave/requests/{asked.json()['id']}/approve", json={})).status_code == 200
    return {"owner": owner, "karim": karim, "design": design, "sales": sales, "karim_id": karim_id}


async def test_the_overview_adds_up(client: httpx.AsyncClient) -> None:
    s = await setup(client)
    owner = s["owner"]
    mon, *_, sun = week()
    response = await report(owner, mon, sun)
    assert response.status_code == 200, response.text
    data = response.json()

    head = data["headcount"]
    assert (head["active"], head["joined"], head["left"]) == (3, 0, 0)
    assert {(d["name"], d["people"]) for d in head["by_department"]} == {
        ("Design", 1),
        ("Sales", 1),
        (None, 1),
    }

    # Expected: Karim 5 days, Salma 4 (one on leave). Present: 5 + 3. The owner joined
    # today (no joining date, no clock-ins back then), so isn't expected that week.
    att = data["attendance"]
    assert (att["working_days"], att["expected"], att["present"], att["late"]) == (5, 9, 8, 2)
    assert att["rate"] == round(8 / 9, 4)
    assert att["average_minutes"] == 480
    assert [d["day"] for d in att["days"]] == [str(d) for d in week() if d.weekday() not in (3, 4)]
    assert att["most_late"] == [{"employee_id": s["karim_id"], "name": "Karim", "count": 2}]

    leave = data["leave"]
    assert (leave["days_taken"], leave["away_today"], leave["pending"]) == (1, 0, 0)
    assert [(t["name"], t["days"]) for t in leave["by_type"]] == [("Casual leave", 1)]


async def test_lateness_follows_the_settings(client: httpx.AsyncClient) -> None:
    s = await setup(client)
    owner = s["owner"]
    settings = (await owner.get("/v1/attendance/settings")).json()
    assert (settings["day_starts_at"], settings["late_after_minutes"]) == ("09:00:00", 15)
    changed = await owner.put(
        "/v1/attendance/settings",
        json={"location_mode": "record", "day_starts_at": "09:30", "late_after_minutes": 5},
    )
    assert changed.status_code == 200, changed.text
    mon, *_, sun = week()
    assert (await report(owner, mon, sun)).json()["attendance"]["late"] == 2  # 09:40 > 09:35
    await owner.put("/v1/attendance/settings", json={"location_mode": "record", "late_after_minutes": 15})
    assert (await report(owner, mon, sun)).json()["attendance"]["late"] == 0  # 09:40 < 09:45
    # Leaving the new fields out keeps them.
    kept = (await owner.put("/v1/attendance/settings", json={"location_mode": "off"})).json()
    assert (kept["day_starts_at"], kept["late_after_minutes"]) == ("09:30:00", 15)
    bad = await owner.put("/v1/attendance/settings", json={"location_mode": "off", "late_after_minutes": 999})
    assert bad.status_code == 422


async def test_tasks_and_new_joiners_count_in_the_period(client: httpx.AsyncClient) -> None:
    s = await setup(client)
    owner = s["owner"]
    now = today("Asia/Dhaka")
    for title, due in (("Overdue one", now - timedelta(days=2)), ("Finished", now)):
        task = (
            await owner.post(
                "/v1/tasks", json={"title": title, "assignee_id": s["karim_id"], "due_date": str(due)}
            )
        ).json()
        if title == "Finished":
            await owner.post(f"/v1/tasks/{task['id']}/move", json={"status": "done"})
    await owner.post("/v1/people", json={"full_name": "New Person", "joined_on": str(now)})
    data = (await report(owner, now - timedelta(days=6), now)).json()
    assert (data["tasks"]["open"], data["tasks"]["overdue"], data["tasks"]["done"]) == (1, 1, 1)
    assert data["tasks"]["most_overdue"][0]["name"] == "Karim"
    assert (data["headcount"]["active"], data["headcount"]["joined"]) == (4, 1)
    # Switched-off modules leave their section out.
    await owner.put("/v1/workspace/modules", json={"modules": ["attendance"]})
    data = (await report(owner, now, now)).json()
    assert data["tasks"] is None
    assert data["leave"] is None
    assert data["attendance"] is not None


async def test_managers_see_their_departments_only(client: httpx.AsyncClient) -> None:
    s = await setup(client)
    owner, design, sales = s["owner"], s["design"], s["sales"]
    manager = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    mon, *_, sun = week()
    mine = (await report(manager, mon, sun)).json()
    assert mine["headcount"]["active"] == 2  # Karim and the manager
    assert mine["attendance"]["present"] == 5
    assert (await report(manager, mon, sun, department_id=sales["id"])).status_code == 404
    only_design = (await report(owner, mon, sun, department_id=design["id"])).json()
    assert only_design["headcount"]["active"] == 2
    assert (await report(s["karim"], mon, sun)).status_code == 403
    assert (await report(owner, sun, mon)).status_code == 422
    assert (await report(owner, mon, mon + timedelta(days=400))).status_code == 422


async def test_people_without_a_joining_date_count_from_when_they_were_added(
    client: httpx.AsyncClient,
) -> None:
    owner = await signup(client)
    now = today("Asia/Dhaka")
    # A whole year, for a workspace made today: only today can count as expected.
    data = (await report(owner, now.replace(month=1, day=1), now)).json()
    assert data["attendance"]["expected"] <= 1
