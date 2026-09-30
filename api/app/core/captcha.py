"""Cloudflare Turnstile verification (a challenge shown after repeated failed sign-ins)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def enabled() -> bool:
    return bool(get_settings().turnstile_secret.get_secret_value())


async def verify(token: str | None, ip: str | None) -> bool:
    if not enabled():
        return True
    if not token:
        return False
    data = {"secret": get_settings().turnstile_secret.get_secret_value(), "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(VERIFY_URL, data=data)
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        return False
