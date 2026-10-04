"""`Idempotency-Key` for writes: send the same key again (a retry after a timeout, say)
and you get the first response back instead of doing the work twice.

Keys belong to whoever sent them (an API key, or a signed-in session), last 24 hours, and
can't be reused for a different request. While the first request is still running, a
retry gets 409. Responses that failed on our side (5xx) aren't kept, so a retry runs again.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, LargeBinary, SmallInteger, String, delete, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.db import open_session
from app.core.models import Base
from app.core.security.tokens import decode_access_token

HEADER = "idempotency-key"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_KEY = 200
# Bigger responses aren't kept (the request isn't replayable; it still runs once).
MAX_STORED = 1_000_000
KEPT_HEADERS = {"content-type", "location", "etag"}
API_KEY_PREFIX = "cmk_"


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(MAX_KEY), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    # None while the first request is still running.
    status: Mapped[int | None] = mapped_column(SmallInteger)
    headers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    body: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


_CLAIM = text(
    """
    INSERT INTO idempotency_keys (scope, key, request_hash, headers, created_at)
    VALUES (:scope, :key, :hash, '{}'::jsonb, now())
    ON CONFLICT (scope, key) DO UPDATE SET
      request_hash = EXCLUDED.request_hash, status = NULL, body = NULL,
      headers = '{}'::jsonb, created_at = now()
    WHERE idempotency_keys.created_at < now() - interval '24 hours'
    RETURNING true
    """
)


def scope_for(authorization: str) -> str | None:
    """Who the key belongs to: the API key, or the signed-in session (stable across
    access-token refreshes). None when the caller isn't signed in."""
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    if token.startswith(API_KEY_PREFIX):
        subject = f"key:{token}"
    else:
        claims = decode_access_token(token)
        if claims is None:
            return None
        subject = f"session:{claims.session_id}"
    return hashlib.sha256(subject.encode()).hexdigest()


def request_hash(method: str, path: str, query: bytes, body: bytes) -> str:
    digest = hashlib.sha256()
    for part in (method.encode(), path.encode(), query, body):
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _problem(status: int, code: str, title: str) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    body = json.dumps(
        {
            "type": f"https://companymgmt.app/problems/{code}",
            "title": title,
            "status": status,
            "detail": title,
            "code": code,
        }
    ).encode()
    return status, [(b"content-type", b"application/problem+json")], body


async def _respond(send: Send, status: int, headers: list[tuple[bytes, bytes]], body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [*headers, (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        key = headers.get(HEADER)
        owner = scope_for(headers.get("authorization", "")) if key is not None else None
        if key is None or owner is None or not scope.get("path", "").startswith("/v1/"):
            await self.app(scope, receive, send)
            return
        if not (0 < len(key) <= MAX_KEY) or not key.isascii() or not key.isprintable():
            await _respond(
                send, *_problem(400, "idempotency_key_invalid", "Idempotency-Key must be 1-200 characters.")
            )
            return

        # Read the body (already size-limited by the request middleware) so it can be
        # hashed, then hand it to the app unchanged.
        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)
        body = b"".join(chunks)
        fingerprint = request_hash(scope["method"], scope["path"], scope.get("query_string", b""), body)

        async with open_session() as db:
            claimed = (await db.execute(_CLAIM, {"scope": owner, "key": key, "hash": fingerprint})).first()
            await db.commit()
            if claimed is None:
                record = await db.scalar(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.scope == owner, IdempotencyRecord.key == key
                    )
                )
                if record is not None:
                    db.expunge(record)
        if claimed is None:
            await self._replay(send, record, fingerprint)
            return

        sent = False

        async def replay_receive() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        status = 500
        kept: dict[str, str] = {}
        captured: list[bytes] = []
        size = 0

        async def capture(message: Message) -> None:
            nonlocal status, size
            if message["type"] == "http.response.start":
                status = int(message["status"])
                for name, value in message.get("headers", []):
                    if name.decode().lower() in KEPT_HEADERS:
                        kept[name.decode().lower()] = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                size += len(chunk)
                if size <= MAX_STORED:
                    captured.append(chunk)
            await send(message)

        try:
            await self.app(scope, replay_receive, capture)
        finally:
            await self._finish(owner, key, status, kept, b"".join(captured), size)

    @staticmethod
    async def _replay(send: Send, record: IdempotencyRecord | None, fingerprint: str) -> None:
        if record is None:
            await _respond(send, *_problem(409, "idempotency_in_progress", "Try again in a moment."))
        elif record.request_hash != fingerprint:
            await _respond(
                send,
                *_problem(
                    422,
                    "idempotency_key_reused",
                    "This Idempotency-Key was used for a different request.",
                ),
            )
        elif record.status is None:
            await _respond(
                send,
                *_problem(
                    409, "idempotency_in_progress", "The first request with this key is still running."
                ),
            )
        else:
            headers = [(k.encode(), v.encode()) for k, v in (record.headers or {}).items()]
            headers.append((b"idempotent-replayed", b"true"))
            await _respond(send, record.status, headers, record.body or b"")

    @staticmethod
    async def _finish(
        owner: str, key: str, status: int, headers: dict[str, str], body: bytes, size: int
    ) -> None:
        async with open_session() as db:
            if status >= 500 or size > MAX_STORED:
                await db.execute(
                    delete(IdempotencyRecord).where(
                        IdempotencyRecord.scope == owner, IdempotencyRecord.key == key
                    )
                )
            else:
                record = await db.get(IdempotencyRecord, (owner, key))
                if record is not None:
                    record.status = status
                    record.headers = headers
                    record.body = body
            await db.commit()
