"""Documents and policies: files people can read, with versions and acknowledgements.

Who may see a document is stored with it (everyone, some roles, some departments), so a
later permission-aware search can filter on the same metadata. Files live in Postgres
with a size limit; a workspace with many large files will move them to object storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.models import Base, IdMixin, TenantScoped, TimestampMixin, Versioned

CATEGORIES = ("policy", "handbook", "sop", "form", "other")


class Document(IdMixin, TenantScoped, TimestampMixin, Versioned, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("category IN ('policy', 'handbook', 'sop', 'form', 'other')", name="category"),
        CheckConstraint("visibility IN ('everyone', 'roles', 'departments')", name="visibility"),
        CheckConstraint("visibility = 'everyone' OR cardinality(visibility_ids) > 0", name="visibility_ids"),
        Index("ix_documents_list", "tenant_id", "archived", "category"),
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(12), default="other")
    visibility: Mapped[str] = mapped_column(String(12), default="everyone")
    # Role ids or department ids (departments include everything below them).
    visibility_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    requires_ack: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))
    current_version_id: Mapped[uuid.UUID | None]
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class DocumentVersion(IdMixin, TenantScoped, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("document_id", "number"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["documents.tenant_id", "documents.id"], ondelete="CASCADE"
        ),
        CheckConstraint("size > 0", name="size"),
    )

    document_id: Mapped[uuid.UUID]
    number: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    # Loaded only when someone downloads it.
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    note: Mapped[str | None] = mapped_column(String(500))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]


class DocumentAck(TenantScoped, Base):
    """Someone confirmed they read a version. A new version asks again."""

    __tablename__ = "document_acks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "version_id"],
            ["document_versions.tenant_id", "document_versions.id"],
            ondelete="CASCADE",
        ),
        Index("ix_document_acks_user", "tenant_id", "user_id"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    acked_at: Mapped[datetime]


class DocumentPassage(IdMixin, TenantScoped, Base):
    """A searchable passage of a document's current version (rebuilt on each upload)."""

    __tablename__ = "document_passages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["documents.tenant_id", "documents.id"], ondelete="CASCADE"
        ),
        Index("ix_document_passages_document", "tenant_id", "document_id"),
        Index("ix_document_passages_search", "search", postgresql_using="gin"),
    )

    document_id: Mapped[uuid.UUID]
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # "simple": no stemming, so Bangla works as well as English.
    search: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True))
