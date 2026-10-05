"""CompanyMgmt API client.

    from companymgmt import CompanyMgmt, verify_webhook

    cm = CompanyMgmt(api_key="cmk_...")
    for member in cm.paginate("/members"):
        print(member["name"])
    cm.post("/branches", {"name": "Uttara"})  # retried safely with an Idempotency-Key

Errors raise CompanyMgmtError with `.status`, `.code` and the full `.problem`.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx

__all__ = ["CompanyMgmt", "CompanyMgmtError", "verify_webhook"]

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


class CompanyMgmtError(Exception):
    def __init__(self, problem: dict[str, Any]) -> None:
        self.problem = problem
        self.status = int(problem.get("status", 0))
        self.code = str(problem.get("code", "error"))
        super().__init__(problem.get("detail") or problem.get("title") or f"HTTP {self.status}")


class CompanyMgmt:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://companymgmt.app/v1",
        max_retries: int = 3,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.startswith("cmk_"):
            raise ValueError("Pass an API key (cmk_...).")
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CompanyMgmt:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        if_match: int | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers: dict[str, str] = {}
        if if_match is not None:
            headers["If-Match"] = f'W/"{if_match}"'
        if method != "GET":
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        params = {k: v for k, v in (params or {}).items() if v is not None}
        attempt = 0
        while True:
            try:
                response = self._client.request(method, path, params=params, json=json, headers=headers)
            except httpx.TransportError:
                if attempt >= self.max_retries:
                    raise
                response = None
            if response is not None and response.is_success:
                if response.status_code == 204 or not response.content:
                    return None
                return response.json() if "json" in response.headers.get("content-type", "") else response.text
            if response is not None and (response.status_code not in RETRYABLE or attempt >= self.max_retries):
                try:
                    problem = {"status": response.status_code, **response.json()}
                except ValueError:
                    problem = {"status": response.status_code}
                raise CompanyMgmtError(problem)
            retry_after = float(response.headers.get("retry-after", 0) or 0) if response is not None else 0
            time.sleep(retry_after if retry_after > 0 else min(8.0, 0.25 * 2**attempt))
            attempt += 1

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, json: Any = None, *, idempotency_key: str | None = None) -> Any:
        return self.request("POST", path, json=json, idempotency_key=idempotency_key)

    def put(self, path: str, json: Any, *, if_match: int | None = None) -> Any:
        return self.request("PUT", path, json=json, if_match=if_match)

    def patch(self, path: str, json: Any, *, if_match: int | None = None) -> Any:
        return self.request("PATCH", path, json=json, if_match=if_match)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def paginate(self, path: str, **params: Any) -> Iterator[dict[str, Any]]:
        cursor = None
        while True:
            page = self.get(path, **params, cursor=cursor)
            yield from page["items"]
            cursor = page.get("next_cursor")
            if not cursor:
                return


def verify_webhook(
    secret: str, body: bytes, header: str, *, tolerance: int = 300, now: float | None = None
) -> bool:
    """Check `CompanyMgmt-Signature` against the raw request body."""
    try:
        parts = dict(item.strip().split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
    except (KeyError, ValueError):
        return False
    if abs((now if now is not None else time.time()) - timestamp) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))
