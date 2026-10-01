"""Domain events: written with the change, delivered to subscribers, never rewritten."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events, outbox
from app.core.time import today
from app.jobs import maintenance
from tests.conftest import owner_dsn
from tests.helpers import Account, add_staff, invite_and_join, signup

NEXT = today("Asia/Dhaka").year + 1


@pytest.fixture
def subscribers() -> Iterator[None]:
    """Subscribers registered in a test don't outlive it."""
    now = {k: list(v) for k, v in events._now.items()}
    later = {k: list(v) for k, v in events._later.items()}
    yield
    events._now.clear()
    events._now.update(now)
    events._later.clear()
    events._later.update(later)


def logged(owner_sql: psycopg.Connection, tenant_id: str) -> list[tuple[Any, ...]]:
    owner_sql.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))
    return owner_sql.execute(
        "SELECT name, subject_type, subject_id, actor_user_id, data FROM domain_events"
        " WHERE tenant_id = %s ORDER BY occurred_at, id",
        (tenant_id,),
    ).fetchall()


async def ask_leave(account: Account, day: int = 3) -> dict[str, Any]:
    types = (await account.get("/v1/leave/types")).json()
    casual = next(t["id"] for t in types if t["name"] == "Casual leave")
    start = str(date(NEXT, 3, day))
    response = await account.post(
        "/v1/leave/requests", json={"leave_type_id": casual, "start_date": start, "end_date": start}
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_leave_flow_is_logged(client: httpx.AsyncClient, owner_sql: psycopg.Connection) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    _, staff = await add_staff(owner, name="Rahim")
    first = await ask_leave(staff)
    assert (await manager.post(f"/v1/leave/requests/{first['id']}/approve", json={})).status_code == 200
    rows = logged(owner_sql, owner.tenant_id)
    assert [r[0] for r in rows] == ["leave.requested", "leave.approved"]
    _, subject_type, subject_id, actor, data = rows[1]
    assert (subject_type, subject_id) == ("leave_request", first["id"])
    assert str(actor) == manager.me["id"]
    assert data["employee_name"] == "Rahim"
    assert data["start_date"] == str(date(NEXT, 3, 3))


async def test_subscribers_run_in_the_transaction(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection, subscribers: None
) -> None:
    owner = await signup(client)
    seen: list[str] = []

    @events.on("leave.*")
    async def note(db: AsyncSession, event: events.Event) -> None:
        seen.append(event.name)

    await ask_leave(owner)
    assert seen == ["leave.requested"]

    # A subscriber that fails takes the change down with it: nothing is half-done.
    @events.on("leave.requested")
    async def broken(db: AsyncSession, event: events.Event) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await ask_leave(owner, day=10)
    assert len((await owner.get("/v1/leave/requests")).json()) == 1
    assert [r[0] for r in logged(owner_sql, owner.tenant_id)] == ["leave.requested"]


async def test_later_subscribers_go_through_the_outbox(client: httpx.AsyncClient, subscribers: None) -> None:
    owner = await signup(client)
    got: list[tuple[str, str]] = []

    @events.on("*", later=True)
    async def mail(db: AsyncSession, event: events.Event) -> None:
        got.append((event.name, str(event.tenant_id)))

    await ask_leave(owner)
    assert got == []
    await outbox.dispatch()
    assert got == [("leave.requested", owner.tenant_id)]


async def test_events_follow_audit_retention(
    client: httpx.AsyncClient, owner_sql: psycopg.Connection
) -> None:
    owner = await signup(client)
    await ask_leave(owner)
    owner_sql.execute(
        "UPDATE subscriptions SET status = 'active', trial_plan_key = NULL WHERE tenant_id = %s",
        (owner.tenant_id,),
    )
    far = datetime.now(UTC) + timedelta(days=31)
    maintenance.apply_audit_retention(psycopg.connect(owner_dsn(), autocommit=True), far)
    assert logged(owner_sql, owner.tenant_id) == []
