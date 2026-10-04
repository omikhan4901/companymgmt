"""What an automation can be made of. Everything is checked here, so a stored automation
(typed by hand or drafted by the assistant) is always one the engine can run safely."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schema import In, Name

# Events an automation can start from: name -> who the event is about (a data key holding
# a membership id), so "the person it's about" can be notified or given a task.
EVENTS: dict[str, str | None] = {
    "member.joined": "membership_id",
    "leave.requested": "membership_id",
    "leave.approved": "membership_id",
    "leave.rejected": "membership_id",
    "leave.cancelled": "membership_id",
    "task.assigned": "assignee_membership_id",
    "task.completed": "assignee_membership_id",
    "task.commented": "assignee_membership_id",
    "attendance.correction_requested": "membership_id",
    "document.published": None,
    "document.acknowledged": "membership_id",
    "announcement.published": None,
    "payroll.finalized": None,
}
Event = Literal[
    "member.joined",
    "leave.requested",
    "leave.approved",
    "leave.rejected",
    "leave.cancelled",
    "task.assigned",
    "task.completed",
    "task.commented",
    "attendance.correction_requested",
    "document.published",
    "document.acknowledged",
    "announcement.published",
    "payroll.finalized",
]
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
PLACEHOLDER = re.compile(r"{([a-z_]+(?:\.[a-z_]+)?)}")
MAX_ACTIONS = 5


class ScheduleTrigger(BaseModel):
    type: Literal["schedule"] = "schedule"
    # "workdays" skips the workspace's weekly days off (from the leave settings).
    every: Literal["day", "workdays", "week", "month"]
    time: str = "09:00"
    # ISO weekday for "week" (1 = Monday); day of the month for "month".
    weekday: int = Field(default=1, ge=1, le=7)
    day: int = Field(default=1, ge=1, le=28)

    @field_validator("time")
    @classmethod
    def _time(cls, value: str) -> str:
        if not TIME.match(value):
            raise ValueError("Use a 24-hour time like 09:00.")
        return value


class EventTrigger(BaseModel):
    type: Literal["event"] = "event"
    event: Event


Trigger = Annotated[ScheduleTrigger | EventTrigger, Field(discriminator="type")]


class Condition(BaseModel):
    """Compares a value from the event (e.g. "days", "type", "department_id")."""

    field: Annotated[str, Field(pattern=r"^[a-z_]{1,40}$")]
    op: Literal["eq", "ne", "gte", "lte", "contains"]
    value: str | float | int | bool = Field(union_mode="left_to_right")


class Recipients(BaseModel):
    """Who: everyone, people with a role, a department, chosen people, the person the event
    is about, people with overdue tasks, or people who haven't clocked in today."""

    kind: Literal["everyone", "role", "department", "people", "subject", "overdue_tasks", "not_clocked_in"]
    role: str | None = Field(default=None, max_length=40)
    department_id: uuid.UUID | None = None
    membership_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _complete(self) -> Recipients:
        if self.kind == "role" and not self.role:
            raise ValueError("Choose a role.")
        if self.kind == "department" and not self.department_id:
            raise ValueError("Choose a department.")
        if self.kind == "people" and not self.membership_ids:
            raise ValueError("Choose at least one person.")
        return self


class NotifyAction(BaseModel):
    type: Literal["notify"] = "notify"
    to: Recipients
    # Placeholders: {name} (the person told), {count} (their overdue tasks), and event
    # values like {event.title} or {event.employee_name}.
    message: Annotated[str, Field(min_length=1, max_length=500)]


class TaskAction(BaseModel):
    type: Literal["create_task"] = "create_task"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = Field(default=None, max_length=5000)
    # One task per person in `for` (or for the automation's owner when empty).
    assign_to: Recipients | None = None
    due_in_days: int | None = Field(default=None, ge=0, le=365)


Action = Annotated[NotifyAction | TaskAction, Field(discriminator="type")]


class AutomationIn(In):
    name: Name
    trigger: Trigger
    conditions: list[Condition] = Field(default_factory=list, max_length=10)
    actions: list[Action] = Field(min_length=1, max_length=MAX_ACTIONS)
    enabled: bool = False
    # Set by the editor when the assistant drafted it (shown and audited).
    drafted_by_ai: bool = False

    @model_validator(mode="after")
    def _fits(self) -> AutomationIn:
        scheduled = isinstance(self.trigger, ScheduleTrigger)
        if scheduled and self.conditions:
            raise ValueError("Conditions only apply to automations that start from an event.")
        for action in self.actions:
            people = action.to if isinstance(action, NotifyAction) else action.assign_to
            if people and people.kind == "subject" and scheduled:
                raise ValueError("“The person it's about” only works when starting from an event.")
            if people and people.kind == "subject" and EVENTS.get(getattr(self.trigger, "event", "")) is None:
                raise ValueError("This event isn't about one person.")
        return self


class AutomationPatch(In):
    name: Name | None = None
    enabled: bool | None = None


class AutomationOut(BaseModel):
    id: uuid.UUID
    name: str
    enabled: bool
    trigger: Trigger
    conditions: list[Condition]
    actions: list[Action]
    owner_membership_id: uuid.UUID
    owner_name: str | None
    drafted_by_ai: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    paused_reason: str | None
    version: int


class AutomationRunOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: str
    cause: str
    detail: list[dict[str, object]]
    error: str | None


class EventInfo(BaseModel):
    name: str
    about_a_person: bool
