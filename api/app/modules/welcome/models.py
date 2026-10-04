"""What sample data added, so it can all be removed again."""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin


class SampleRecord(IdMixin, TenantScoped, TimestampMixin, Base):
    __tablename__ = "sample_records"

    table_name: Mapped[str] = mapped_column(String(60))
    record_id: Mapped[uuid.UUID]
    position: Mapped[int] = mapped_column(Integer)
