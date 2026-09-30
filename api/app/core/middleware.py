"""Request id, client info, security headers and request size limits (pure ASGI)."""

from __future__ import annotations

import hmac
import json
import secrets
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import context
from app.core.config import get_settings

MAX_JSON_BYTES = 1_000_000
MAX_UPLOAD_BYTES = 10_000_000

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cache-control", b"no-store"),
]


def _problem(status: int, code: str, title: str) -> bytes:
    return json.dumps(
        {
            "type": f"https://companymgmt.app/problems/{code}",
            "title": title,
            "status": status,
            "detail": title,
            "code": code,
        }
    ).encode()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.trust_proxy = settings.trust_proxy_headers
        self.proxy_token = settings.proxy_token.get_secret_value().encode()
        self.hsts = settings.is_production_like

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = secrets.token_hex(8)
        ip = scope.get("client", (None,))[0] if scope.get("client") else None
        if self.proxy_token:
            via_proxy = hmac.compare_digest(headers.get("x-cm-proxy-token", "").encode(), self.proxy_token)
            if via_proxy:
                ip = headers.get("x-cm-client-ip") or ip
            elif scope.get("path", "").startswith("/v1/"):
                await self._reject(
                    send, 403, "direct_access", "Use the web address, not the API address.", request_id
                )
                return
        elif self.trust_proxy and headers.get("x-forwarded-for"):
            # Cloud Run / Cloudflare append the real client; take the left-most entry.
            ip = headers["x-forwarded-for"].split(",")[0].strip()
        context.bind(
            context.RequestInfo(request_id=request_id, ip=ip, user_agent=headers.get("user-agent", "")[:300])
        )
        state: dict[str, Any] = scope.setdefault("state", {})
        state["request_id"] = request_id
        started = time.perf_counter()

        # Size limits: reject early from Content-Length, and count streamed bytes too.
        content_type = headers.get("content-type", "")
        limit = MAX_UPLOAD_BYTES if content_type.startswith("multipart/") else MAX_JSON_BYTES
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(send, 413, "too_large", "The request is too large.", request_id)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge()
            return message

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra = list(_SECURITY_HEADERS)
                extra.append((b"x-request-id", request_id.encode()))
                extra.append(
                    (b"server-timing", f"app;dur={(time.perf_counter() - started) * 1000:.0f}".encode())
                )
                if self.hsts:
                    extra.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    (k, v) for k, v in extra if k not in existing
                ]
            await send(message)

        try:
            await self.app(scope, limited_receive, send_with_headers)
        except _TooLarge:
            await self._reject(send, 413, "too_large", "The request is too large.", request_id)

    @staticmethod
    async def _reject(send: Send, status: int, code: str, title: str, request_id: str) -> None:
        body = _problem(status, code, title)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"x-request-id", request_id.encode()),
                    *_SECURITY_HEADERS,
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _TooLarge(Exception):
    pass
