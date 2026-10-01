"""The daily email digest: one email per person listing what they haven't read.

Only notifications at least an hour old and never emailed are included, so something
already seen in the app isn't emailed, and nothing is emailed twice. People without an
email address (staff accounts) and people who turned digests off get nothing.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from typing import Any

from sqlalchemy import select, update

from app.core import outbox
from app.core.db import open_session
from app.core.email import Mail, as_payload
from app.core.time import utcnow
from app.modules.notifications.models import Notification
from app.modules.platform.emails import link
from app.modules.platform.models import Membership, Tenant, User

GRACE = timedelta(hours=1)
SHOWN = 10

_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "bn": [
        "জানুয়ারি",
        "ফেব্রুয়ারি",
        "মার্চ",
        "এপ্রিল",
        "মে",
        "জুন",
        "জুলাই",
        "আগস্ট",
        "সেপ্টেম্বর",
        "অক্টোবর",
        "নভেম্বর",
        "ডিসেম্বর",
    ],
}
_LONG_MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

# The same sentences the web app shows (web/src/i18n), kept short for email.
_KINDS: dict[str, dict[str, str]] = {
    "en": {
        "leave_requested": "{name} asked for {type}: {dates}",
        "leave_approved": "{actor} approved your {type}: {dates}",
        "leave_rejected": "{actor} turned down your {type}: {dates}",
        "leave_cancelled_yours": "{actor} cancelled your {type}: {dates}",
        "leave_withdrawn": "{name} withdrew their {type} request: {dates}",
        "attendance_correction_requested": "{name} asked for a time fix",
        "attendance_correction_approved": "{actor} approved your time fix",
        "attendance_correction_rejected": "{actor} turned down your time fix",
        "payroll_submitted": "{actor} sent {period} payroll for approval",
        "payroll_finalized": "Your payslip for {period} is ready",
        "other": "Something changed",
    },
    "bn": {
        "leave_requested": "{name} {type} চেয়েছেন: {dates}",
        "leave_approved": "{actor} আপনার {type} মঞ্জুর করেছেন: {dates}",
        "leave_rejected": "{actor} আপনার {type} নামঞ্জুর করেছেন: {dates}",
        "leave_cancelled_yours": "{actor} আপনার {type} বাতিল করেছেন: {dates}",
        "leave_withdrawn": "{name} তাঁর {type}-এর অনুরোধ তুলে নিয়েছেন: {dates}",
        "attendance_correction_requested": "{name} সময় ঠিক করার অনুরোধ করেছেন",
        "attendance_correction_approved": "{actor} আপনার সময় ঠিক করার অনুরোধ মঞ্জুর করেছেন",
        "attendance_correction_rejected": "{actor} আপনার সময় ঠিক করার অনুরোধ নামঞ্জুর করেছেন",
        "payroll_submitted": "{actor} {period}-এর বেতন অনুমোদনের জন্য পাঠিয়েছেন",
        "payroll_finalized": "{period}-এর পে-স্লিপ তৈরি",
        "other": "কিছু পরিবর্তন হয়েছে",
    },
}
_TEXT = {
    "en": {
        "subject_one": "1 update in {workspace}",
        "subject": "{count} updates in {workspace}",
        "hi": "Hi {name},",
        "intro": "Here's what you haven't seen yet in {workspace}:",
        "more": "…and {count} more.",
        "open": "Open CompanyMgmt: {link}",
        "stop": "Don't want these emails? Turn them off in your account: {link}",
        "someone": "Someone",
    },
    "bn": {
        "subject_one": "{workspace}-এ ১টি নতুন খবর",
        "subject": "{workspace}-এ {count}টি নতুন খবর",
        "hi": "প্রিয় {name},",
        "intro": "{workspace}-এ যা এখনও দেখেননি:",
        "more": "…আরও {count}টি।",
        "open": "CompanyMgmt খুলুন: {link}",
        "stop": "এই ইমেইল চান না? অ্যাকাউন্ট থেকে বন্ধ করুন: {link}",
        "someone": "কেউ একজন",
    },
}


def _num(value: int | str, lang: str) -> str:
    return str(value).translate(_DIGITS) if lang == "bn" else str(value)


def _day(value: Any, lang: str) -> str:
    try:
        d = date.fromisoformat(str(value))
    except ValueError:
        return ""
    return f"{_num(d.day, lang)} {_MONTHS[lang][d.month - 1]}"


def _period(value: Any, lang: str) -> str:
    try:
        year, month = (int(p) for p in str(value).split("-"))
    except ValueError:
        return ""
    name = _LONG_MONTHS_EN[month - 1] if lang == "en" else _MONTHS["bn"][month - 1]
    return f"{name} {_num(year, lang)}"


def describe(n: Notification, lang: str, membership_id: uuid.UUID | None) -> str:
    data = n.data or {}
    start, end = data.get("start_date"), data.get("end_date")
    dates = (
        _day(start, lang)
        if start and (not end or end == start)
        else f"{_day(start, lang)} – {_day(end, lang)}"  # noqa: RUF001
    )
    values = {
        "actor": n.actor_name or _TEXT[lang]["someone"],
        "name": data.get("employee_name") or _TEXT[lang]["someone"],
        "type": data.get("type") or "",
        "dates": dates if start else "",
        "period": _period(data.get("period"), lang),
    }
    key = n.kind.replace(".", "_")
    if n.kind == "leave.cancelled":
        key = (
            "leave_cancelled_yours"
            if str(data.get("membership_id")) == str(membership_id)
            else "leave_withdrawn"
        )
    template = _KINDS[lang].get(key, _KINDS[lang]["other"])
    return template.format(**values)


def compose(to: str, name: str, lang: str, workspace: str, lines: list[str], hidden: int) -> dict[str, Any]:
    t = _TEXT[lang if lang in _TEXT else "en"]
    count = len(lines) + hidden
    subject = (t["subject_one"] if count == 1 else t["subject"]).format(
        workspace=workspace, count=_num(count, lang)
    )
    body = [t["hi"].format(name=name), "", t["intro"].format(workspace=workspace), ""]
    body += [f"• {line}" for line in lines]
    if hidden:
        body += [t["more"].format(count=_num(hidden, lang))]
    body += ["", t["open"].format(link=link("/app")), "", t["stop"].format(link=link("/app/account"))]
    text = "\n".join(body)
    items = "".join(f"<li>{escape(line)}</li>" for line in lines)
    html = (
        f"<p>{escape(t['hi'].format(name=name))}</p>"
        f"<p>{escape(t['intro'].format(workspace=workspace))}</p><ul>{items}</ul>"
        + (f"<p>{escape(t['more'].format(count=_num(hidden, lang)))}</p>" if hidden else "")
        + f'<p><a href="{escape(link("/app"))}">CompanyMgmt</a></p>'
        + f'<p style="color:#666;font-size:13px">{escape(t["stop"].format(link=link("/app/account")))}</p>'
    )
    return as_payload(Mail(to=to, subject=subject, text=text, html=html))


async def send_digests(now: datetime | None = None) -> int:
    """Queue one digest per person who has something unread. Returns emails queued."""
    now = now or utcnow()
    async with open_session() as db:
        tenants = list(
            (await db.execute(select(Tenant.id, Tenant.name).where(Tenant.status == "active"))).all()
        )
    sent = 0
    for tenant_id, workspace in tenants:
        async with open_session(tenant_id) as db:
            rows = (
                await db.execute(
                    select(Notification, User, Membership.id)
                    .join(User, User.id == Notification.user_id)
                    .join(
                        Membership,
                        (Membership.user_id == User.id) & (Membership.tenant_id == Notification.tenant_id),
                    )
                    .where(
                        Notification.read_at.is_(None),
                        Notification.emailed_at.is_(None),
                        Notification.created_at <= now - GRACE,
                        Membership.status == "active",
                        User.email.is_not(None),
                        User.email_digest.is_(True),
                    )
                    .order_by(Notification.created_at.desc())
                )
            ).all()
            if not rows:
                continue
            per_user: dict[uuid.UUID, list[tuple[Notification, User, uuid.UUID]]] = defaultdict(list)
            for note, user, membership_id in rows:
                per_user[user.id].append((note, user, membership_id))
            for items in per_user.values():
                user, membership_id = items[0][1], items[0][2]
                lang = user.locale if user.locale in _TEXT else "en"
                lines = [describe(n, lang, membership_id) for n, _, _ in items[:SHOWN]]
                assert user.email is not None
                outbox.enqueue(
                    db,
                    "email.send",
                    compose(user.email, user.name, lang, workspace, lines, len(items) - len(lines)),
                    tenant_id=tenant_id,
                )
                sent += 1
            await db.execute(
                update(Notification)
                .where(Notification.id.in_([n.id for n, _, _ in rows]))
                .values(emailed_at=now)
            )
            ids = outbox.pending_ids(db)
            await db.commit()
        await outbox.dispatch(ids)
    return sent
