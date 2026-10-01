"""M3's finish line: a 30-person agency runs a week of work entirely in the product.

The week itself is scripts/agency_week.py, the same one used to fill a demo workspace and
by the browser test; here we check what it should have left behind.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.core import ratelimit
from scripts.agency_week import PROJECTS, play_week


async def test_a_thirty_person_agency_runs_a_week(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Thirty people sign in from the test's one address.
    monkeypatch.setattr(ratelimit, "LOGIN_IP", ratelimit.Rule("login-ip", 1000, 300))
    started = time.monotonic()
    week = await play_week(client, leave_for_browser=True)
    assert time.monotonic() - started < 60  # sign-ins included
    owner, admin, joiner = week.people["owner"], week.people["shirin"], week.people["mitu"]
    policy = week.documents["policy"]

    people = (await owner.get("/v1/people", params={"status": "active", "limit": 200}))["items"]
    assert len(people) == 30
    summary = week.summary()
    assert len(summary["people"]) == 29

    # Thursday afternoon, what the browser test finishes: one reader and one decision left.
    acks = await owner.get(f"/v1/documents/{policy}/acknowledgements")
    assert (acks["acknowledged"], acks["total"]) == (29, 30)
    nusrat, reader = week.people[summary["waiting_manager"]], week.people[summary["last_reader"]]
    [waiting] = (await nusrat.get("/v1/approvals"))["items"]
    assert waiting["employee_name"] == "Fahim Shahriar"
    await reader.post(f"/v1/announcements/{week.announcement_id}/read")
    await reader.post(f"/v1/documents/{policy}/acknowledge")
    await nusrat.post(f"/v1/approvals/leave/{waiting['id']}/approve", json={})

    # A policy acknowledged by everyone, and the week's note read by everyone.
    acks = await owner.get(f"/v1/documents/{policy}/acknowledgements")
    assert (acks["acknowledged"], acks["total"]) == (30, 30)
    receipts = await owner.get(f"/v1/announcements/{week.announcement_id}/receipts")
    assert (receipts["read"], receipts["total"]) == (30, 30)
    for person in week.people.values():
        assert await person.get("/v1/documents/to-acknowledge") == []
        assert (await person.get("/v1/announcements/unread"))["unread"] == 0

    # Leave approved through the inbox, and nothing left waiting on anyone.
    approved = await owner.get("/v1/leave/requests", params={"status": "approved"})
    assert len(approved) == 4
    for person in week.people.values():
        assert (await person.get("/v1/approvals"))["items"] == []
    told = [n["kind"] for n in (await week.people["mahmud"].get("/v1/notifications"))["items"]]
    assert "leave.approved" in told

    # The client work moved on the boards.
    projects = {p["name"]: p for p in await owner.get("/v1/projects")}
    for _dept, name, _color, tasks in PROJECTS:
        done = sum(1 for *_, status in tasks if status == "done")
        assert (projects[name]["done_tasks"], projects[name]["open_tasks"]) == (done, len(tasks) - done)

    # The joiner's checklist started by itself; reading the policy ticked its item off.
    [run] = await admin.get("/v1/onboarding/runs")
    assert (run["employee_name"], run["done"], run["total"]) == ("Mitu Chowdhury", 1, 3)
    assert {t["title"] for t in await joiner.get("/v1/tasks/my-work")} == {"Lunch with the team"}
