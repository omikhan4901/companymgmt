"""Automations: built by owners and admins, run as their owner, recorded, limited, never
looping, and drafted from plain words by the assistant for review."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest

from app.ai import provider
from app.ai.fake import FakeModel
from app.ai.provider import Reply, ToolCall
from app.core import outbox
from app.modules.automations.engine import matches, next_run, render, tick
from app.modules.automations.schemas import Condition, ScheduleTrigger
from tests.helpers import Account, add_staff, if_match, signup
from tests.test_ai import switch_on

OVERDUE = {
    "name": "Overdue reminder",
    "trigger": {"type": "schedule", "every": "week", "weekday": 1, "time": "09:00"},
    "actions": [
        {
            "type": "notify",
            "to": {"kind": "overdue_tasks"},
            "message": "Hi {name}, you have {count} overdue tasks.",
        }
    ],
    "enabled": True,
}


async def employee_id(account: Account) -> str:
    return str((await account.get("/v1/leave/balances")).json()["employee_id"])


async def inbox(account: Account) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = (await account.get("/v1/notifications")).json()["items"]
    return items


def test_schedules_land_on_the_right_local_time() -> None:
    after = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)  # a Sunday, 18:00 in Dhaka
    weekly = ScheduleTrigger(every="week", weekday=1, time="09:00")
    assert next_run(weekly, "Asia/Dhaka", after, []) == datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    daily = ScheduleTrigger(every="day", time="20:00")
    assert next_run(daily, "Asia/Dhaka", after, []) == datetime(2026, 10, 4, 14, 0, tzinfo=UTC)
    # Workdays skip the workspace's weekly days off (Friday and Saturday here).
    friday = datetime(2026, 10, 8, 23, 0, tzinfo=UTC)  # Friday 05:00 in Dhaka
    workdays = ScheduleTrigger(every="workdays", time="09:00")
    # Friday 9 and Saturday 10 October are off: Sunday 11th, 09:00 in Dhaka (03:00Z).
    assert next_run(workdays, "Asia/Dhaka", friday, [5, 6]) == datetime(2026, 10, 11, 3, 0, tzinfo=UTC)
    monthly = ScheduleTrigger(every="month", day=1, time="08:00")
    assert next_run(monthly, "Asia/Dhaka", after, []) == datetime(2026, 11, 1, 2, 0, tzinfo=UTC)


def test_conditions_and_placeholders() -> None:
    data = {"days": 3, "type": "Sick leave", "employee_name": "Rafiq"}
    assert matches([Condition(field="days", op="gte", value=2)], data)
    assert not matches([Condition(field="days", op="lte", value=2)], data)
    assert matches([Condition(field="type", op="contains", value="sick")], data)
    assert not matches([Condition(field="type", op="eq", value="Casual leave")], data)
    assert not matches([Condition(field="missing", op="gte", value=1)], data)
    assert render("Hi {name}: {event.employee_name} asked, {unknown} stays", None, None) == (
        "Hi {name}: {event.employee_name} asked, {unknown} stays"
    )


async def test_only_owners_and_admins_build_automations(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    assert (await staff.get("/v1/automations")).status_code == 403
    assert (await staff.post("/v1/automations", json=OVERDUE)).status_code == 403
    created = await owner.post("/v1/automations", json=OVERDUE)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["next_run_at"] is not None
    assert body["owner_name"]
    # Things that can't work are refused before they're saved.
    subject_on_schedule = {
        **OVERDUE,
        "actions": [{"type": "notify", "to": {"kind": "subject"}, "message": "Hi"}],
    }
    assert (await owner.post("/v1/automations", json=subject_on_schedule)).status_code == 422
    bad_time = {**OVERDUE, "trigger": {"type": "schedule", "every": "day", "time": "25:00"}}
    assert (await owner.post("/v1/automations", json=bad_time)).status_code == 422
    no_role = {
        **OVERDUE,
        "actions": [{"type": "notify", "to": {"kind": "role", "role": "pilot"}, "message": "x"}],
    }
    assert (await owner.post("/v1/automations", json=no_role)).status_code == 422
    # Pausing clears the schedule; the editor needs the current version.
    paused = (await owner.patch(f"/v1/automations/{body['id']}", json={"enabled": False})).json()
    assert paused["next_run_at"] is None
    stale = await owner.put(f"/v1/automations/{body['id']}", json=OVERDUE, headers=if_match(1))
    assert stale.status_code == 412
    log = (await owner.get("/v1/audit")).json()["items"]
    assert {"automation.created", "automation.paused"} <= {e["action"] for e in log}


async def test_a_scheduled_reminder_tells_each_person_their_own_count(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rafiq")
    _, other = await add_staff(owner, name="Salma")
    yesterday = str(datetime.now(UTC).date() - timedelta(days=3))
    for title in ("Invoices", "Stock count"):
        made = await owner.post(
            "/v1/tasks", json={"title": title, "assignee_id": await employee_id(staff), "due_date": yesterday}
        )
        assert made.status_code == 201, made.text
    automation = (await owner.post("/v1/automations", json=OVERDUE)).json()
    ran = await owner.post(f"/v1/automations/{automation['id']}/run")
    assert ran.status_code == 200, ran.text
    assert ran.json()["status"] == "ok"
    assert ran.json()["detail"] == [{"action": "notify", "count": 1}]
    [note] = [n for n in await inbox(staff) if n["kind"] == "automation.message"]
    assert note["data"]["title"] == "Hi Rafiq, you have 2 overdue tasks."
    assert [n for n in await inbox(other) if n["kind"] == "automation.message"] == []
    runs = (await owner.get(f"/v1/automations/{automation['id']}/runs")).json()
    assert [r["cause"] for r in runs] == ["manual"]


async def test_events_start_automations_without_loops(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rafiq")
    # Whenever a task is assigned, give the same person a follow-up task. Its own task
    # assignment must not start it again.
    follow_up = {
        "name": "Follow up",
        "trigger": {"type": "event", "event": "task.assigned"},
        "actions": [
            {"type": "create_task", "title": "Check: {event.title}", "assign_to": {"kind": "subject"}},
        ],
        "enabled": True,
    }
    created = await owner.post("/v1/automations", json=follow_up)
    assert created.status_code == 201, created.text
    await owner.post("/v1/tasks", json={"title": "Paint the sign", "assignee_id": await employee_id(staff)})
    for _ in range(3):
        await outbox.dispatch()
    titles = sorted(t["title"] for t in (await staff.get("/v1/tasks/my-work")).json())
    assert titles == ["Check: Paint the sign", "Paint the sign"]
    runs = (await owner.get(f"/v1/automations/{created.json()['id']}/runs")).json()
    assert [(r["cause"], r["status"]) for r in runs] == [("task.assigned", "ok")]


async def test_conditions_filter_events(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner)
    long_leave = {
        "name": "Long leave alert",
        "trigger": {"type": "event", "event": "leave.requested"},
        "conditions": [{"field": "days", "op": "gte", "value": 3}],
        "actions": [
            {
                "type": "notify",
                "to": {"kind": "role", "role": "owner"},
                "message": "{event.employee_name}: long leave",
            }
        ],
        "enabled": True,
    }
    assert (await owner.post("/v1/automations", json=long_leave)).status_code == 201
    kind = (await staff.get("/v1/leave/types")).json()[0]["id"]
    start = datetime.now(UTC).date() + timedelta(days=14)
    one = await staff.post(
        "/v1/leave/requests", json={"leave_type_id": kind, "start_date": str(start), "end_date": str(start)}
    )
    assert one.status_code == 201, one.text
    await outbox.dispatch()
    assert [n for n in await inbox(owner) if n["kind"] == "automation.message"] == []
    end = start + timedelta(days=9)
    long = await staff.post(
        "/v1/leave/requests",
        json={"leave_type_id": kind, "start_date": str(start + timedelta(days=7)), "end_date": str(end)},
    )
    assert long.status_code == 201, long.text
    await outbox.dispatch()
    notes = [n for n in await inbox(owner) if n["kind"] == "automation.message"]
    assert len(notes) == 1
    assert notes[0]["data"]["title"].endswith(": long leave")


async def test_runaway_and_orphaned_automations_pause_themselves(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    automation = (await owner.post("/v1/automations", json=OVERDUE)).json()
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    owner_sql.execute(
        "INSERT INTO automation_runs"
        " (id, tenant_id, automation_id, status, cause, detail, created_at, updated_at)"
        " SELECT gen_random_uuid(), tenant_id, id, 'ok', 'manual', '[]', now(), now()"
        " FROM automations, generate_series(1, 30)"
    )
    limited = (await owner.post(f"/v1/automations/{automation['id']}/run")).json()
    assert limited["status"] == "limited"
    after = (await owner.get(f"/v1/automations/{automation['id']}")).json()
    assert (after["enabled"], after["next_run_at"]) == (False, None)
    assert "too many times" in after["paused_reason"]
    # Switching it back on clears the reason (and makes you its owner).
    again = (await owner.patch(f"/v1/automations/{automation['id']}", json={"enabled": True})).json()
    assert (again["enabled"], again["paused_reason"]) == (True, None)


async def test_the_tick_runs_what_is_due_and_reschedules(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    automation = (await owner.post("/v1/automations", json=OVERDUE)).json()
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (owner.tenant_id,))
    owner_sql.execute("UPDATE automations SET next_run_at = now() - interval '1 minute'")
    assert await tick() == 1
    after = (await owner.get(f"/v1/automations/{automation['id']}")).json()
    assert datetime.fromisoformat(after["next_run_at"]) > datetime.now(UTC)
    assert after["last_run_at"] is not None
    assert await tick() == 0  # nothing due any more


@pytest.fixture
def fake() -> Iterator[FakeModel]:
    model = FakeModel()
    provider.use_model(model)
    yield model
    provider.use_model(None)


async def test_the_assistant_drafts_automations_for_review(
    client: httpx.AsyncClient, fake: FakeModel
) -> None:
    owner = await signup(client)
    await switch_on(owner, ["ask", "automations"])
    draft = {k: v for k, v in OVERDUE.items() if k != "enabled"}
    broken = {**draft, "trigger": {"type": "schedule", "every": "fortnight"}}
    fake.script = [
        Reply(tool_calls=[ToolCall("automation_draft", broken)]),
        Reply(tool_calls=[ToolCall("automation_draft", {**draft, "enabled": True})], text="Here it is."),
    ]
    result = await owner.post(
        "/v1/ai/automations/draft", json={"text": "Every Monday remind people of overdue work"}
    )
    assert result.status_code == 200, result.text
    body = result.json()
    # The first try didn't fit and was sent back; the second is switched off for review.
    assert body["automation"]["enabled"] is False
    assert body["automation"]["drafted_by_ai"] is True
    system, turns, offered = fake.calls[-1]
    assert [t.name for t in offered] == ["automation_draft"]
    assert "Roles:" in system
    assert turns[-1].role == "tool"
    # Nothing was saved until the person saves it.
    assert (await owner.get("/v1/automations")).json() == []
    saved = await owner.post("/v1/automations", json=body["automation"])
    assert saved.json()["drafted_by_ai"] is True
    # Staff can't draft automations.
    _, staff = await add_staff(owner)
    assert (await staff.post("/v1/ai/automations/draft", json={"text": "x"})).status_code == 403
