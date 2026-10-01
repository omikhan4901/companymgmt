"""Document shapes, shared by the REST routes and capabilities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.core.schema import In, Name, Out, Text

Category = Literal["policy", "handbook", "sop", "form", "other"]
Visibility = Literal["everyone", "roles", "departments"]
Title = Annotated[Name, Field(max_length=200)]
Description = Annotated[Text, Field(max_length=5000)]


class DocumentIn(In):
    title: Title
    description: Description | None = None
    category: Category = "other"
    visibility: Visibility = "everyone"
    visibility_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    requires_ack: bool = False


class DocumentPatch(In):
    title: Title | None = None
    description: Description | None = None
    category: Category | None = None
    visibility: Visibility | None = None
    visibility_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    requires_ack: bool | None = None
    archived: bool | None = None


class AudienceRef(Out):
    id: uuid.UUID
    name: str


class VersionOut(Out):
    id: uuid.UUID
    number: int
    filename: str
    content_type: str
    size: int
    note: str | None
    uploaded_by_name: str | None
    created_at: datetime


class DocumentOut(Out):
    id: uuid.UUID
    title: str
    description: str | None
    category: Category
    visibility: Visibility
    visibility_names: list[AudienceRef]
    requires_ack: bool
    archived: bool
    current: VersionOut | None
    # Whether the caller has acknowledged the current version (null when none is asked).
    acknowledged: bool | None
    # For managers: how many of the people it's for have acknowledged the current version.
    reach: int | None
    ack_count: int | None
    can_manage: bool
    updated_at: datetime
    version: int


class DocumentDetail(DocumentOut):
    versions: list[VersionOut]


class AckPerson(Out):
    employee_id: uuid.UUID
    name: str
    department: str | None
    acked_at: datetime | None


class AcksOut(Out):
    version_number: int | None
    total: int
    acknowledged: int
    people: list[AckPerson]
