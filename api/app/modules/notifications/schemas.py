from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    actor_name: str | None
    subject_type: str | None
    subject_id: str | None
    link: str | None
    data: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class InboxOut(BaseModel):
    items: list[NotificationOut]
    unread: int
    next_cursor: str | None


class UnreadOut(BaseModel):
    unread: int
