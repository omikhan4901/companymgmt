"""Reports by email: weekly and monthly, once, as the subscriber would see them."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import httpx

from app.core import email
from app.core.time import today
from app.modules.reports.subscriptions import period, send_reports
from tests.helpers import Account, add_staff, invite_and_join, role_id, signup

MORNING = time(3, 0)  # 09:00 in Dhaka


def mails_to(addr: str | None) -> list[email.Mail]:
    return [m for m in email.sent if m.to == addr]


def next_week_start(account: Account) -> datetime:
    start = int(account.me["workspace"]["week_start"])
    day = today("Asia/Dhaka") + timedelta(days=1)
    while day.isoweekday() != start:
        day += timedelta(days=1)
    return datetime.combine(day, MORNING, UTC)


def next_month_start() -> datetime:
    now = today("Asia/Dhaka")
    first = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
    return datetime.combine(first, MORNING, UTC)


async def subscribe(account: Account, **body: object) -> httpx.Response:
    return await account.put("/v1/reports/subscription", json=body)


def test_reports_are_due_on_the_first_day_of_the_week_or_month() -> None:
    monday = date(2026, 9, 28)
    assert period("weekly", monday, 1) == (date(2026, 9, 21), date(2026, 9, 27))
    assert period("weekly", monday, 6) is None
    assert period("monthly", date(2026, 10, 1), 1) == (date(2026, 9, 1), date(2026, 9, 30))
    assert period("monthly", date(2027, 3, 1), 1) == (date(2027, 2, 1), date(2027, 2, 28))
    assert period("monthly", date(2026, 10, 2), 1) is None


async def test_weekly_and_monthly_reports_are_sent_once(client: httpx.AsyncClient) -> None:
    owner = await signup(client, business="Nokshi Digital")
    assert (await owner.get("/v1/reports/subscription")).json() == {
        "weekly": False,
        "monthly": False,
        "department_id": None,
        "has_email": True,
    }
    saved = await subscribe(owner, weekly=True)
    assert saved.json()["weekly"] is True
    email.sent.clear()
    week = next_week_start(owner)
    assert await send_reports(week - timedelta(days=1)) == 0  # not the first day of the week
    assert await send_reports(week) == 1
    [mail] = mails_to(owner.email)
    start = (week - timedelta(days=7)).date()
    assert mail.subject.startswith(f"Nokshi Digital: the week of {start.day} ")
    assert "People: 1 (0 joined, 0 left)" in mail.text
    assert "Attendance: " in mail.text
    assert "/app/reports" in mail.text
    assert "<li>People: 1" in mail.html
    # Once a day, however often the job runs.
    assert await send_reports(week + timedelta(hours=1)) == 0

    await subscribe(owner, weekly=False, monthly=True)
    email.sent.clear()
    month = next_month_start()
    assert await send_reports(month) == 1
    [monthly] = mails_to(owner.email)
    assert "Nokshi Digital: " in monthly.subject
    assert "the week of" not in monthly.subject
    # Turned off: nothing more.
    await subscribe(owner)
    assert (await owner.get("/v1/reports/subscription")).json()["monthly"] is False
    assert await send_reports(month + timedelta(days=31)) == 0


async def test_reports_are_worked_out_as_the_subscriber(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    design = (await owner.post("/v1/departments", json={"name": "Design"})).json()
    sales = (await owner.post("/v1/departments", json={"name": "Sales"})).json()
    await add_staff(owner, name="Karim", scope_department_id=design["id"])
    await add_staff(owner, name="Salma", scope_department_id=sales["id"])
    manager = await invite_and_join(owner, role="manager", scope_department_id=design["id"])
    assert (await manager.patch("/v1/auth/me", json={"locale": "bn"})).status_code == 204
    assert (await subscribe(manager, weekly=True, department_id=sales["id"])).status_code == 404
    assert (await subscribe(manager, weekly=True)).status_code == 200
    assert (await subscribe(owner, weekly=True, department_id=design["id"])).status_code == 200
    email.sent.clear()
    assert await send_reports(next_week_start(owner)) == 2
    [theirs] = mails_to(manager.email)
    assert "কর্মী: ২ জন" in theirs.text  # Karim and the manager, not Salma
    [mine] = mails_to(owner.email)
    assert "how Design did" in mine.text

    # Staff accounts have no email; people who lose access to reports get nothing.
    _, staff_manager = await add_staff(owner, name="Rafiq", role="manager", scope_department_id=design["id"])
    refused = await subscribe(staff_manager, weekly=True)
    assert (refused.status_code, refused.json()["code"]) == (422, "no_email")
    assert (await staff_manager.get("/v1/reports/subscription")).json()["has_email"] is False
    members = (await owner.get("/v1/members")).json()["items"]
    member = next(m for m in members if m["id"] == manager.membership_id)
    demoted = await owner.patch(
        f"/v1/members/{member['id']}",
        json={"role_id": await role_id(owner, "employee")},
        headers={"if-match": f'W/"{member["version"]}"'},
    )
    assert demoted.status_code == 200, demoted.text
    email.sent.clear()
    assert await send_reports(next_week_start(owner) + timedelta(days=7)) == 1
    assert mails_to(manager.email) == []
