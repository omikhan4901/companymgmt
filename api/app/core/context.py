"""Per-request information available anywhere (logging, audit) without passing it around."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class RequestInfo:
    request_id: str = ""
    ip: str | None = None
    user_agent: str | None = None
    user_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    membership_id: uuid.UUID | None = None
    extra: dict[str, str] = field(default_factory=dict)


_current: ContextVar[RequestInfo | None] = ContextVar("request_info", default=None)


def current() -> RequestInfo:
    info = _current.get()
    if info is None:
        info = RequestInfo()
        _current.set(info)
    return info


def bind(info: RequestInfo) -> None:
    _current.set(info)
