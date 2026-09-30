"""Declarative base and shared column types."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, Uuid, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, declared_attr, mapped_column

from app.core.ids import uuid7

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {datetime: DateTime(timezone=True), uuid.UUID: Uuid()}


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TenantScoped:
    """Rows that belong to one tenant. The table gets forced RLS in its migration.

    Subclasses must also declare `UniqueConstraint("tenant_id", "id")` so other tables can
    point at them with composite foreign keys (see the plan, §3.3).
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(index=True)


class Versioned:
    """Optimistic concurrency: stale writes are rejected (API answers 412)."""

    version: Mapped[int] = mapped_column(default=1)

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        return {"version_id_col": cls.__table__.c.version}  # type: ignore[attr-defined]


@event.listens_for(Session, "before_flush")
def _stamp_tenant(session: Session, flush_context: object, instances: object) -> None:
    tenant = session.info.get("tenant_id")
    for obj in session.new:
        if isinstance(obj, TenantScoped):
            if obj.tenant_id is None:
                if tenant is None:
                    raise RuntimeError(f"Cannot create {type(obj).__name__} without a tenant.")
                obj.tenant_id = tenant
            elif tenant is not None and obj.tenant_id != tenant:
                raise RuntimeError("Object tenant does not match the session tenant.")
