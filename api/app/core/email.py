"""Outgoing email. Always sent through the outbox (topic `email.send`)."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib.parse import unquote, urlparse

import anyio

from app.core.config import get_settings
from app.core.outbox import handler

log = logging.getLogger("app.email")


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None


# Messages "sent" with the memory backend (tests read them).
sent: list[Mail] = []


def _send_smtp(mail: Mail) -> None:
    settings = get_settings()
    url = urlparse(settings.smtp_url.get_secret_value())
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = mail.to
    msg["Subject"] = mail.subject
    msg.set_content(mail.text)
    if mail.html:
        msg.add_alternative(mail.html, subtype="html")
    context = ssl.create_default_context()
    port = url.port or (465 if url.scheme == "smtps" else 587)
    if url.scheme == "smtps":
        server: smtplib.SMTP = smtplib.SMTP_SSL(url.hostname or "", port, context=context, timeout=15)
    else:
        server = smtplib.SMTP(url.hostname or "", port, timeout=15)
        server.starttls(context=context)
    with server:
        if url.username:
            server.login(unquote(url.username), unquote(url.password or ""))
        server.send_message(msg)


async def deliver(mail: Mail) -> None:
    backend = get_settings().email_backend
    if backend == "memory":
        sent.append(mail)
    elif backend == "console":
        log.info("Email to %s: %s\n%s", mail.to, mail.subject, mail.text)
        sent.append(mail)
    else:
        await anyio.to_thread.run_sync(_send_smtp, mail)


@handler("email.send")
async def _on_email(payload: dict[str, Any]) -> None:
    await deliver(Mail(**payload))


def as_payload(mail: Mail) -> dict[str, Any]:
    return {"to": mail.to, "subject": mail.subject, "text": mail.text, "html": mail.html}
