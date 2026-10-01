"""Announcement shapes, shared by the REST routes and capabilities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.core.schema import In, Name, Out, Text

Audience = Literal["everyone", "branches", "departments"]
Title = Annotated[Name, Field(max_length=200)]
Body = Annotated[Text, Field(min_length=1, max_length=20000)]


class AnnouncementIn(In):
    title: Title
    body: Body
    audience: Audience = "everyone"
    audience_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    pinned: bool = False


class AnnouncementPatch(In):
    title: Title | None = None
    body: Body | None = None
    audience: Audience | None = None
    audience_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    pinned: bool | None = None


class AudienceRef(Out):
    id: uuid.UUID
    name: str


class AnnouncementOut(Out):
    id: uuid.UUID
    title: str
    body: str
    audience: Audience
    audience_names: list[AudienceRef]
    pinned: bool
    published_at: datetime
    edited_at: datetime | None
    author_name: str | None
    read: bool
    # Filled in for people who may see receipts (the author, and posters in scope).
    reach: int | None
    read_count: int | None
    can_edit: bool
    version: int


class ReceiptOut(Out):
    employee_id: uuid.UUID
    name: str
    department: str | None
    read_at: datetime | None


class ReceiptsOut(Out):
    total: int
    read: int
    people: list[ReceiptOut]


class UnreadOut(Out):
    unread: int
