"""Task and project shapes, shared by the REST routes and capabilities."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schema import In, Name, Out, ShortName, Text

Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Status = Literal["todo", "doing", "done"]
Priority = Literal["low", "normal", "high", "urgent"]
LongText = Annotated[Text, Field(max_length=5000)]
Title = Annotated[Name, Field(max_length=200)]
ItemText = Annotated[Name, Field(max_length=300)]


class PersonRef(Out):
    id: uuid.UUID
    name: str


class ProjectIn(In):
    name: ShortName
    description: LongText | None = None
    department_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    color: Color = "#6d28d9"
    due_date: date | None = None


class ProjectPatch(In):
    name: ShortName | None = None
    description: LongText | None = None
    department_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)
    color: Color | None = None
    due_date: date | None = None
    status: Literal["active", "archived"] | None = None


class ProjectOut(Out):
    id: uuid.UUID
    name: str
    description: str | None
    department_id: uuid.UUID | None
    members: list[PersonRef]
    status: Literal["active", "archived"]
    color: str
    due_date: date | None
    open_tasks: int
    done_tasks: int
    overdue_tasks: int
    can_manage: bool
    version: int


class ChecklistItemOut(Out):
    id: uuid.UUID
    text: str
    done: bool


class TaskIn(In):
    title: Title
    description: LongText | None = None
    project_id: uuid.UUID | None = None
    # Leave out for yourself.
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    due_date: date | None = None
    priority: Priority = "normal"
    status: Status = "todo"
    checklist: list[ItemText] = Field(default_factory=list, max_length=100)


class TaskPatch(In):
    title: Title | None = None
    description: LongText | None = None
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    due_date: date | None = None
    no_due_date: bool = False
    priority: Priority | None = None
    status: Status | None = None


class MoveIn(In):
    status: Status
    # Put the card after this one in the column (none: at the top).
    after_id: uuid.UUID | None = None


class TaskOut(Out):
    id: uuid.UUID
    title: str
    description: str | None
    project_id: uuid.UUID | None
    project_name: str | None
    status: Status
    priority: Priority
    assignee: PersonRef | None
    due_date: date | None
    overdue: bool
    position: float
    completed_at: datetime | None
    created_at: datetime
    created_by_name: str | None
    checklist_done: int
    checklist_total: int
    comments: int
    can_delete: bool
    version: int


class TaskDetail(TaskOut):
    checklist: list[ChecklistItemOut]


class ChecklistIn(In):
    text: ItemText


class ChecklistPatch(In):
    text: ItemText | None = None
    done: bool | None = None


class CommentIn(In):
    body: Annotated[Name, Field(max_length=5000)]


class CommentOut(Out):
    id: uuid.UUID
    author_name: str | None
    mine: bool
    body: str
    created_at: datetime
