"""HTTP helpers: ETags for optimistic concurrency and cursor encoding."""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import Request, Response

from app.core.errors import AppError, Invalid, PreconditionFailed


class PreconditionRequired(AppError):
    status, code, title = 428, "if_match_required", "Send If-Match with the version you edited"


def etag(version: int) -> str:
    return f'W/"{version}"'


def set_etag(response: Response, version: int) -> None:
    response.headers["ETag"] = etag(version)


def check_if_match(request: Request, version: int) -> None:
    """Edits must say which version they started from; a stale one is rejected (412)."""
    header = request.headers.get("if-match")
    if not header:
        raise PreconditionRequired()
    candidates = {h.strip() for h in header.split(",")}
    if "*" in candidates:
        return
    if etag(version) not in candidates and f'"{version}"' not in candidates:
        raise PreconditionFailed()


def encode_cursor(values: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(values, default=str).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Invalid("Bad cursor.", code="bad_cursor") from exc
    if not isinstance(data, dict):
        raise Invalid("Bad cursor.", code="bad_cursor")
    return data


async def read_body(request: Request, limit: int, *, message: str, code: str) -> bytes:
    """The request body, refused as soon as it passes `limit` bytes."""
    if int(request.headers.get("content-length") or 0) > limit:
        raise Invalid(message, code=code)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise Invalid(message, code=code)
        chunks.append(chunk)
    return b"".join(chunks)
