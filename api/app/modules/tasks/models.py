"""Tasks and projects: projects with members, tasks on a board, checklists and comments."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

STATUSES = ("todo", "doing", "done")
PRIORITIES = ("low", "normal", "high", "urgent")


class Project(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "department_id"], ["departments.tenant_id", "departments.id"]),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="color"),
        Index("ix_projects_status", "tenant_id", "status"),
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    # Optional home department: managers with tasks.manage see projects in their scope.
    department_id: Mapped[uuid.UUID | None]
    # People on the project (employee ids). Members see it and work on its tasks.
    member_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    status: Mapped[str] = mapped_column(String(10), default="active")
    color: Mapped[str] = mapped_column(String(7), default="#6d28d9")
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Task(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "project_id"], ["projects.tenant_id", "projects.id"]),
        ForeignKeyConstraint(["tenant_id", "assignee_id"], ["employees.tenant_id", "employees.id"]),
        CheckConstraint("status IN ('todo', 'doing', 'done')", name="status"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="priority"),
        CheckConstraint("(status = 'done') = (completed_at IS NOT NULL)", name="completed"),
        Index("ix_tasks_project", "tenant_id", "project_id", "status", "position"),
        Index("ix_tasks_assignee", "tenant_id", "assignee_id", "status", "due_date"),
    )

    # None: a task on its own (someone's personal to-do, or one handed to a person).
    project_id: Mapped[uuid.UUID | None]
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="todo")
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    assignee_id: Mapped[uuid.UUID | None]
    due_date: Mapped[date | None] = mapped_column(Date)
    # Order within its board column; new cards go to the bottom.
    position: Mapped[float] = mapped_column(Float, default=0)
    completed_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Onboarding checklists (M3.7) mark the tasks they created.
    source: Mapped[str | None] = mapped_column(String(40))


class ChecklistItem(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "task_checklist_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "task_id"], ["tasks.tenant_id", "tasks.id"], ondelete="CASCADE"),
        Index("ix_task_checklist_task", "tenant_id", "task_id", "position"),
    )

    task_id: Mapped[uuid.UUID]
    text: Mapped[str] = mapped_column(String(300))
    done: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))
    position: Mapped[float] = mapped_column(Float, default=0)


class TaskComment(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "task_id"], ["tasks.tenant_id", "tasks.id"], ondelete="CASCADE"),
        Index("ix_task_comments_task", "tenant_id", "task_id", "created_at"),
    )

    task_id: Mapped[uuid.UUID]
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
