"""The daily digest: unread notifications by email, once, in the person's language."""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from app.core import email
from app.core.time import utcnow
from app.modules.notifications.digest import send_digests
from tests.helpers import add_staff, invite_and_join, signup
from tests.test_notifications import ask_leave, inbox, leave_day

LATER = timedelta(hours=2)


def mails_to(addr: str | None) -> list[email.Mail]:
    return [m for m in email.sent if m.to == addr]


async def test_unread_notifications_are_emailed_once(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    _, staff = await add_staff(owner, name="Rahim")
    await ask_leave(staff)
    await ask_leave(staff, 7)
    # Too fresh: people may still see it in the app.
    assert await send_digests() == 0
    # The manager already read theirs; the owner didn't.
    assert (await manager.post("/v1/notifications/read-all")).status_code == 200
    email.sent.clear()
    assert await send_digests(utcnow() + LATER) == 1
    [mail] = mails_to(owner.email)
    assert mail.subject.startswith("2 updates in ")
    day = leave_day()
    assert f"Rahim asked for Casual leave: {day.day} Mar" in mail.text
    assert "/app/account" in mail.text
    assert "<li>" in mail.html
    assert mails_to(manager.email) == []
    # Never twice, and still unread in the app.
    assert await send_digests(utcnow() + LATER) == 0
    assert (await inbox(owner))["unread"] == 2


async def test_digest_speaks_the_persons_language_and_can_be_turned_off(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    manager = await invite_and_join(owner, role="manager")
    assert (await manager.patch("/v1/auth/me", json={"locale": "bn"})).status_code == 204
    assert (await owner.patch("/v1/auth/me", json={"email_digest": False})).status_code == 204
    assert (await owner.get("/v1/auth/me")).json()["email_digest"] is False
    _, staff = await add_staff(owner, name="Rahim")
    await ask_leave(staff)
    email.sent.clear()
    assert await send_digests(utcnow() + LATER) == 1
    [mail] = mails_to(manager.email)
    assert "১টি নতুন খবর" in mail.subject
    assert f"{str(leave_day().day).translate(str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯'))} মার্চ" in mail.text
    assert mails_to(owner.email) == []
    # Staff without an email address are never emailed.
    assert (await staff.get("/v1/auth/me")).json()["email"] is None


async def test_long_digests_are_cut_short(client: httpx.AsyncClient) -> None:
    owner = await signup(client)
    _, staff = await add_staff(owner, name="Rahim")
    types = (await staff.get("/v1/leave/types")).json()
    unpaid = next(t["id"] for t in types if t["name"] == "Unpaid leave")
    day, asked = date(utcnow().year + 1, 1, 1), 0
    while asked < 12:
        body = {"leave_type_id": unpaid, "start_date": str(day), "end_date": str(day)}
        asked += (await staff.post("/v1/leave/requests", json=body)).status_code == 201
        day += timedelta(days=1)
    email.sent.clear()
    await send_digests(utcnow() + LATER)
    [mail] = mails_to(owner.email)
    assert mail.subject.startswith("12 updates")
    assert mail.text.count("• ") == 10
    assert "…and 2 more." in mail.text
