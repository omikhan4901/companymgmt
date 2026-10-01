"""The overview report as an email: the headline numbers, and a link to the full page."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from app.core.email import Mail, as_payload
from app.modules.platform.emails import link
from app.modules.reports.schemas import OverviewOut

_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
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
_TEXT = {
    "en": {
        "weekly": "{workspace}: the week of {start}",
        "monthly": "{workspace}: {month}",
        "hi": "Hi {name},",
        "intro": "Here's how {scope} did from {start} to {end}.",
        "everyone": "everyone",
        "people": "People: {active} ({joined} joined, {left} left)",
        "attendance": "Attendance: {rate} ({present} of {expected} expected days)",
        "late": "Late arrivals: {late}",
        "leave": "Days of leave taken: {days}",
        "tasks": "Overdue tasks: {overdue} ({open} open, {done} done)",
        "most_late": "Late most often: {names}",
        "open": "See the full report: {link}",
        "stop": "To stop these emails, turn them off on the Reports page.",
    },
    "bn": {
        "weekly": "{workspace}: {start} থেকে শুরু হওয়া সপ্তাহ",
        "monthly": "{workspace}: {month}",
        "hi": "প্রিয় {name},",
        "intro": "{start} থেকে {end} পর্যন্ত {scope} কেমন চলেছে।",
        "everyone": "সবাই",
        "people": "কর্মী: {active} জন ({joined} জন যোগ দিয়েছেন, {left} জন চলে গেছেন)",
        "attendance": "হাজিরা: {rate} (প্রত্যাশিত {expected} দিনের মধ্যে {present} দিন)",
        "late": "দেরিতে আসা: {late} বার",
        "leave": "নেওয়া ছুটি: {days} দিন",
        "tasks": "মেয়াদোত্তীর্ণ কাজ: {overdue}টি ({open}টি চলমান, {done}টি শেষ)",
        "most_late": "সবচেয়ে বেশি দেরি: {names}",
        "open": "পুরো রিপোর্ট দেখুন: {link}",
        "stop": "এই ইমেইল বন্ধ করতে রিপোর্ট পাতায় গিয়ে বন্ধ করুন।",
    },
}


def _n(value: float | int | str, lang: str) -> str:
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text.translate(_DIGITS) if lang == "bn" else text


def _day(d: date, lang: str) -> str:
    return f"{_n(d.day, lang)} {_MONTHS[lang][d.month - 1]}"


def subject(frequency: str, workspace: str, report: OverviewOut, lang: str) -> str:
    t = _TEXT[lang]
    month = f"{_MONTHS[lang][report.start.month - 1]} {_n(report.start.year, lang)}"
    return t[frequency].format(workspace=workspace, start=_day(report.start, lang), month=month)


def lines(report: OverviewOut, lang: str) -> list[str]:
    t = _TEXT[lang]
    head = report.headcount
    out = [
        t["people"].format(
            active=_n(head.active, lang), joined=_n(head.joined, lang), left=_n(head.left, lang)
        )
    ]
    if report.attendance:
        att = report.attendance
        rate = "—" if att.rate is None else f"{_n(round(att.rate * 100), lang)}%"
        out.append(
            t["attendance"].format(rate=rate, present=_n(att.present, lang), expected=_n(att.expected, lang))
        )
        out.append(t["late"].format(late=_n(att.late, lang)))
        if att.most_late:
            out.append(t["most_late"].format(names=", ".join(p.name for p in att.most_late[:3])))
    if report.leave:
        out.append(t["leave"].format(days=_n(report.leave.days_taken, lang)))
    if report.tasks:
        tasks = report.tasks
        out.append(
            t["tasks"].format(
                overdue=_n(tasks.overdue, lang), open=_n(tasks.open, lang), done=_n(tasks.done, lang)
            )
        )
    return out


def compose(
    to: str, name: str, lang: str, workspace: str, frequency: str, report: OverviewOut, scope: str | None
) -> dict[str, Any]:
    lang = lang if lang in _TEXT else "en"
    t = _TEXT[lang]
    intro = t["intro"].format(
        scope=scope or t["everyone"], start=_day(report.start, lang), end=_day(report.end, lang)
    )
    body = lines(report, lang)
    url = link("/app/reports")
    text = "\n".join(
        [
            t["hi"].format(name=name),
            "",
            intro,
            "",
            *[f"• {line}" for line in body],
            "",
            t["open"].format(link=url),
            "",
            t["stop"],
        ]
    )
    html = (
        f"<p>{escape(t['hi'].format(name=name))}</p><p>{escape(intro)}</p>"
        f"<ul>{''.join(f'<li>{escape(line)}</li>' for line in body)}</ul>"
        f'<p><a href="{escape(url)}">{escape(t["open"].format(link="").rstrip(": "))}</a></p>'
        f'<p style="color:#666;font-size:13px">{escape(t["stop"])}</p>'
    )
    return as_payload(Mail(to=to, subject=subject(frequency, workspace, report, lang), text=text, html=html))
