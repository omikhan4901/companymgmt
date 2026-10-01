"""Email texts in English and Bangla. Kept short and plain."""

from __future__ import annotations

from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import outbox
from app.core.config import get_settings
from app.core.email import Mail, as_payload

_T: dict[str, dict[str, tuple[str, str]]] = {
    "verify": {
        "en": (
            "Confirm your email",
            "Hi {name},\n\nConfirm your email address for CompanyMgmt:\n{link}\n\nThe link works for 48 hours. If you didn't sign up, ignore this email.",
        ),
        "bn": (
            "আপনার ইমেইল নিশ্চিত করুন",
            "প্রিয় {name},\n\nCompanyMgmt-এর জন্য আপনার ইমেইল ঠিকানা নিশ্চিত করুন:\n{link}\n\nলিংকটি ৪৮ ঘণ্টা কাজ করবে। আপনি সাইন আপ না করে থাকলে এই ইমেইলটি উপেক্ষা করুন।",
        ),
    },
    "reset": {
        "en": (
            "Reset your password",
            "Hi {name},\n\nSomeone asked to reset your CompanyMgmt password. If it was you, use this link:\n{link}\n\nIt works for 30 minutes, once. If it wasn't you, you can ignore this email; your password hasn't changed.",
        ),
        "bn": (
            "পাসওয়ার্ড রিসেট করুন",
            "প্রিয় {name},\n\nআপনার CompanyMgmt পাসওয়ার্ড রিসেট করার অনুরোধ এসেছে। আপনি করে থাকলে এই লিংকটি ব্যবহার করুন:\n{link}\n\nলিংকটি ৩০ মিনিট, একবার কাজ করবে। আপনি না করে থাকলে কিছু করতে হবে না; পাসওয়ার্ড বদলায়নি।",
        ),
    },
    "invite": {
        "en": (
            "{inviter} invited you to {workspace}",
            "Hi {name},\n\n{inviter} invited you to join {workspace} on CompanyMgmt.\n\nAccept the invitation:\n{link}\n\nThe link works for 7 days.",
        ),
        "bn": (
            "{inviter} আপনাকে {workspace}-এ আমন্ত্রণ জানিয়েছেন",
            "প্রিয় {name},\n\n{inviter} আপনাকে CompanyMgmt-এ {workspace}-এ যোগ দিতে আমন্ত্রণ জানিয়েছেন।\n\nআমন্ত্রণ গ্রহণ করুন:\n{link}\n\nলিংকটি ৭ দিন কাজ করবে।",
        ),
    },
    "password_changed": {
        "en": (
            "Your password was changed",
            "Hi {name},\n\nYour CompanyMgmt password was just changed and your other devices were signed out. If this wasn't you, reset your password now: {link}",
        ),
        "bn": (
            "আপনার পাসওয়ার্ড বদলানো হয়েছে",
            "প্রিয় {name},\n\nআপনার CompanyMgmt পাসওয়ার্ড এইমাত্র বদলানো হয়েছে এবং অন্যান্য ডিভাইস থেকে সাইন আউট করা হয়েছে। এটি আপনি না করে থাকলে এখনই পাসওয়ার্ড রিসেট করুন: {link}",
        ),
    },
    "mfa_changed": {
        "en": (
            "Two-step verification was {state}",
            "Hi {name},\n\nTwo-step verification on your CompanyMgmt account was just {state}. If this wasn't you, reset your password now: {link}",
        ),
        "bn": (
            "দুই-ধাপের যাচাই {state}",
            "প্রিয় {name},\n\nআপনার CompanyMgmt অ্যাকাউন্টে দুই-ধাপের যাচাই এইমাত্র {state}। এটি আপনি না করে থাকলে এখনই পাসওয়ার্ড রিসেট করুন: {link}",
        ),
    },
    "deletion_scheduled": {
        "en": (
            "{workspace} will be deleted on {date}",
            "Hi {name},\n\nYou asked to delete {workspace} on CompanyMgmt. Nobody can use it now, and on {date} everything in it is deleted for good. We'll email you a deletion certificate then.\n\nChanged your mind? Sign in and restore it before that date: {link}",
        ),
        "bn": (
            "{date} তারিখে {workspace} মুছে ফেলা হবে",
            "প্রিয় {name},\n\nআপনি CompanyMgmt-এ {workspace} মুছে ফেলতে বলেছেন। এখন আর কেউ এটি ব্যবহার করতে পারবেন না, এবং {date} তারিখে এর সবকিছু স্থায়ীভাবে মুছে যাবে। তখন আমরা আপনাকে একটি মুছে ফেলার সনদ ইমেইল করব।\n\nমত বদলেছেন? ওই তারিখের আগে সাইন ইন করে এটি ফিরিয়ে আনুন: {link}",
        ),
    },
    "token_reuse": {
        "en": (
            "We signed you out for safety",
            "Hi {name},\n\nAn old sign-in token for your CompanyMgmt account was used again, which can mean someone copied it. We signed out that device. If you don't recognise this, change your password: {link}",
        ),
        "bn": (
            "নিরাপত্তার জন্য আপনাকে সাইন আউট করা হয়েছে",
            "প্রিয় {name},\n\nআপনার CompanyMgmt অ্যাকাউন্টের একটি পুরনো সাইন-ইন টোকেন আবার ব্যবহার করা হয়েছে, যার মানে কেউ এটি কপি করে থাকতে পারে। আমরা সেই ডিভাইস থেকে সাইন আউট করেছি। আপনি চিনতে না পারলে পাসওয়ার্ড বদলান: {link}",
        ),
    },
}


def link(path: str) -> str:
    return get_settings().web_base_url.rstrip("/") + path


def send(db: AsyncSession, kind: str, to: str, locale: str, **values: str) -> None:
    """Queue an email in the current transaction (sent after commit)."""
    lang = locale if locale in ("en", "bn") else "en"
    subject_t, body_t = _T[kind][lang]
    subject = subject_t.format(**values)
    body = body_t.format(**values)
    html = "<p>" + escape(body).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
    outbox.enqueue(db, "email.send", as_payload(Mail(to=to, subject=subject, text=body, html=html)))
