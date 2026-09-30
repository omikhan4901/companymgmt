"""With a proxy token set, /v1 only answers requests that came through the web proxy, and
the client IP comes from the proxy's header, never from a forgeable X-Forwarded-For."""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core import context, middleware
from app.core.config import get_settings


def build(monkeypatch: pytest.MonkeyPatch, token: str) -> Starlette:
    settings = get_settings().model_copy(
        update={"proxy_token": SecretStr(token), "trust_proxy_headers": True}
    )
    monkeypatch.setattr(middleware, "get_settings", lambda: settings)

    async def whoami(_: Request) -> JSONResponse:
        return JSONResponse({"ip": context.current().ip})

    app = Starlette(routes=[Route("/v1/whoami", whoami), Route("/healthz", whoami)])
    app.add_middleware(middleware.RequestContextMiddleware)
    return app


async def call(app: Starlette, path: str, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, client=("10.0.0.9", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
        return await client.get(path, headers=headers)


async def test_requests_through_the_proxy_use_its_client_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build(monkeypatch, "s3cret-token")
    ok = await call(
        app,
        "/v1/whoami",
        {"x-cm-proxy-token": "s3cret-token", "x-cm-client-ip": "203.0.113.7", "x-forwarded-for": "6.6.6.6"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"ip": "203.0.113.7"}


async def test_direct_requests_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build(monkeypatch, "s3cret-token")
    for headers in (
        {},
        {"x-cm-proxy-token": "wrong"},
        {"x-forwarded-for": "6.6.6.6", "x-cm-client-ip": "6.6.6.6"},
    ):
        response = await call(app, "/v1/whoami", headers)
        assert response.status_code == 403, headers
        assert response.json()["code"] == "direct_access"
    # Health checks still answer directly (Cloud Run probes), with the real peer address.
    health = await call(app, "/healthz", {"x-forwarded-for": "6.6.6.6"})
    assert health.json() == {"ip": "10.0.0.9"}


async def test_without_a_token_nothing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = build(monkeypatch, "")
    response = await call(app, "/v1/whoami", {"x-forwarded-for": "198.51.100.4, 10.1.1.1"})
    assert response.json() == {"ip": "198.51.100.4"}
