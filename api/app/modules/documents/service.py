"""Documents and policies: who sees what, versions, downloads and acknowledgements.

A document is for everyone, for some roles, or for some departments (and the teams
under them). People see the active documents meant for them; `documents.manage`
sees all of them. Acknowledgements belong to a version, so a new version asks again.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core import audit, events
from app.core.errors import Forbidden, Invalid, NotFound
from app.core.time import utcnow
from app.modules.documents import access, files, text
from app.modules.documents.models import Document, DocumentAck, DocumentPassage, DocumentVersion
from app.modules.documents.schemas import (
    AckPerson,
    AcksOut,
    AudienceRef,
    DocumentDetail,
    DocumentIn,
    DocumentOut,
    DocumentPatch,
    PassageOut,
    VersionOut,
)
from app.modules.people.access import ancestors, subtree
from app.modules.people.models import Department, Employee
from app.modules.people.service import employee_for_membership
from app.modules.platform import hooks
from app.modules.platform.deps import Ctx
from app.modules.platform.models import Membership, Role, User


async def _me(ctx: Ctx) -> Employee | None:
    if "documents.me" not in ctx.cache:
        assert ctx.membership is not None
        ctx.cache["documents.me"] = await employee_for_membership(ctx.db, ctx.membership.id)
    found: Employee | None = ctx.cache["documents.me"]
    return found


async def _visible(ctx: Ctx) -> ColumnElement[bool]:
    if ctx.can(access.MANAGE):
        return Document.id.is_not(None)
    assert ctx.role is not None
    me = await _me(ctx)
    above = await ancestors(ctx.db, me.department_id if me else None)
    conditions: list[ColumnElement[bool]] = [
        Document.visibility == "everyone",
        and_(Document.visibility == "roles", Document.visibility_ids.contains([ctx.role.id])),
    ]
    if above:
        conditions.append(and_(Document.visibility == "departments", Document.visibility_ids.overlap(above)))
    return and_(Document.archived.is_(False), Document.current_version_id.is_not(None), or_(*conditions))


async def _reach(db: AsyncSession, doc: Document) -> ColumnElement[bool]:
    """Employees a document is for (active, with a login)."""
    base = and_(Employee.status == "active", Employee.membership_id.is_not(None))
    if doc.visibility == "roles":
        roles = select(Membership.id).where(Membership.role_id.in_(doc.visibility_ids))
        return and_(base, Employee.membership_id.in_(roles))
    if doc.visibility == "departments":
        below: set[uuid.UUID] = set()
        for root in doc.visibility_ids:
            below.update(await subtree(db, root))
        return and_(base, Employee.department_id.in_(below))
    return base


def _version_out(v: DocumentVersion, names: dict[uuid.UUID, str]) -> VersionOut:
    return VersionOut(
        id=v.id,
        number=v.number,
        filename=v.filename,
        content_type=v.content_type,
        size=v.size,
        note=v.note,
        uploaded_by_name=names.get(v.uploaded_by) if v.uploaded_by else None,
        created_at=v.created_at,
    )


async def _names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.name).where(User.id.in_(ids)))).all())


async def _ack_counts(db: AsyncSession, doc: Document) -> tuple[int, int]:
    reach = await _reach(db, doc)
    total = await db.scalar(select(func.count()).select_from(Employee).where(reach))
    acked = await db.scalar(
        select(func.count())
        .select_from(Employee)
        .join(Membership, Membership.id == Employee.membership_id)
        .join(
            DocumentAck,
            and_(DocumentAck.version_id == doc.current_version_id, DocumentAck.user_id == Membership.user_id),
        )
        .where(reach)
    )
    return total or 0, acked or 0


async def _out(ctx: Ctx, docs: Sequence[Document]) -> list[DocumentOut]:
    if not docs:
        return []
    current_ids = [d.current_version_id for d in docs if d.current_version_id]
    versions = {
        v.id: v
        for v in await ctx.db.scalars(select(DocumentVersion).where(DocumentVersion.id.in_(current_ids)))
    }
    mine = set(
        await ctx.db.scalars(
            select(DocumentAck.version_id).where(
                DocumentAck.version_id.in_(current_ids), DocumentAck.user_id == ctx.user.id
            )
        )
    )
    names = await _names(ctx.db, {v.uploaded_by for v in versions.values() if v.uploaded_by})
    targets = {i for d in docs for i in d.visibility_ids}
    labels: dict[uuid.UUID, str] = {}
    if targets:
        labels.update((await ctx.db.execute(select(Role.id, Role.name).where(Role.id.in_(targets)))).all())
        labels.update(
            (
                await ctx.db.execute(select(Department.id, Department.name).where(Department.id.in_(targets)))
            ).all()
        )
    manager = ctx.can(access.MANAGE)
    out = []
    for d in docs:
        current = versions.get(d.current_version_id) if d.current_version_id else None
        reach = acked = None
        if manager and d.requires_ack and current:
            reach, acked = await _ack_counts(ctx.db, d)
        out.append(
            DocumentOut(
                id=d.id,
                title=d.title,
                description=d.description,
                category=d.category,
                visibility=d.visibility,
                visibility_names=[AudienceRef(id=i, name=labels[i]) for i in d.visibility_ids if i in labels],
                requires_ack=d.requires_ack,
                archived=d.archived,
                current=_version_out(current, names) if current else None,
                acknowledged=(current.id in mine) if d.requires_ack and current else None,
                reach=reach,
                ack_count=acked,
                can_manage=manager,
                updated_at=d.updated_at,
                version=d.version,
            )
        )
    return out


async def list_documents(
    ctx: Ctx, *, archived: bool = False, to_acknowledge: bool = False
) -> list[DocumentOut]:
    query = select(Document).where(await _visible(ctx))
    if not archived:
        query = query.where(Document.archived.is_(False))
    if to_acknowledge:
        acked = select(DocumentAck.version_id).where(DocumentAck.user_id == ctx.user.id)
        query = query.where(
            Document.requires_ack.is_(True),
            Document.current_version_id.is_not(None),
            Document.current_version_id.not_in(acked),
            Document.archived.is_(False),
        )
        if ctx.can(access.MANAGE):
            # Managers see everything, but are only asked to acknowledge what's meant for them.
            me = await _me(ctx)
            docs = list(await ctx.db.scalars(query.order_by(func.lower(Document.title))))
            mine = [d for d in docs if await _meant_for(ctx, d, me)]
            return await _out(ctx, mine)
    query = query.order_by(Document.category, func.lower(Document.title))
    return await _out(ctx, list(await ctx.db.scalars(query)))


async def _meant_for(ctx: Ctx, doc: Document, me: Employee | None) -> bool:
    if doc.visibility == "everyone":
        return True
    if doc.visibility == "roles":
        return ctx.role is not None and ctx.role.id in doc.visibility_ids
    return bool(set(doc.visibility_ids) & set(await ancestors(ctx.db, me.department_id if me else None)))


async def _document(ctx: Ctx, document_id: uuid.UUID, *, lock: bool = False) -> Document:
    query = select(Document).where(Document.id == document_id, await _visible(ctx))
    if lock:
        query = query.with_for_update(of=Document)
    doc = await ctx.db.scalar(query)
    if doc is None:
        raise NotFound()
    return doc


async def get(ctx: Ctx, document_id: uuid.UUID) -> DocumentDetail:
    doc = await _document(ctx, document_id)
    out = (await _out(ctx, [doc]))[0]
    rows = list(
        await ctx.db.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.number.desc())
        )
    )
    names = await _names(ctx.db, {v.uploaded_by for v in rows if v.uploaded_by})
    return DocumentDetail(**out.model_dump(), versions=[_version_out(v, names) for v in rows])


async def _check_visibility(ctx: Ctx, visibility: str, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    ids = list(dict.fromkeys(ids))
    if visibility == "everyone":
        return []
    if not ids:
        raise Invalid(errors=[{"field": "visibility_ids", "message": "Choose who should see this."}])
    if visibility == "roles":
        found = set(await ctx.db.scalars(select(Role.id).where(Role.id.in_(ids))))
        if found != set(ids):
            raise Invalid(errors=[{"field": "visibility_ids", "message": "Some of these roles don't exist."}])
        return ids
    for department in ids:
        if not await hooks.valid_department(ctx.db, department):
            raise Invalid(
                errors=[{"field": "visibility_ids", "message": "Some of these departments don't exist."}]
            )
    return ids


async def create(ctx: Ctx, body: DocumentIn) -> DocumentDetail:
    ctx.require(access.MANAGE)
    doc = Document(
        title=body.title,
        description=body.description,
        category=body.category,
        visibility=body.visibility,
        visibility_ids=await _check_visibility(ctx, body.visibility, body.visibility_ids),
        requires_ack=body.requires_ack,
        created_by=ctx.user.id,
    )
    ctx.db.add(doc)
    await ctx.db.flush()
    await audit.record(
        ctx.db, "document.created", target_type="document", target_id=doc.id, data={"title": doc.title}
    )
    await ctx.db.commit()
    return await get(ctx, doc.id)


async def update(ctx: Ctx, document_id: uuid.UUID, body: DocumentPatch) -> DocumentDetail:
    ctx.require(access.MANAGE)
    doc = await _document(ctx, document_id, lock=True)
    if body.visibility is not None or body.visibility_ids is not None:
        visibility = body.visibility or doc.visibility
        ids = body.visibility_ids if body.visibility_ids is not None else list(doc.visibility_ids)
        doc.visibility_ids = await _check_visibility(ctx, visibility, ids)
        doc.visibility = visibility
    for field in ("title", "category", "requires_ack", "archived"):
        value = getattr(body, field)
        if value is not None:
            setattr(doc, field, value)
    if "description" in body.model_fields_set:
        doc.description = body.description
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "document.updated",
        target_type="document",
        target_id=doc.id,
        data=body.model_dump(exclude_unset=True, mode="json", exclude={"description"}),
    )
    await ctx.db.commit()
    return await get(ctx, doc.id)


async def upload(
    ctx: Ctx, document_id: uuid.UUID, filename: str, note: str | None, data: bytes
) -> DocumentDetail:
    """A new version becomes the current one. Everyone it's for hears about it."""
    ctx.require(access.MANAGE)
    doc = await _document(ctx, document_id, lock=True)
    name, content_type, digest = files.check(filename, data)
    number = (
        await ctx.db.scalar(
            select(func.max(DocumentVersion.number)).where(DocumentVersion.document_id == doc.id)
        )
        or 0
    ) + 1
    version = DocumentVersion(
        document_id=doc.id,
        number=number,
        filename=name,
        content_type=content_type,
        size=len(data),
        sha256=digest,
        data=data,
        note=(note or "").strip()[:500] or None,
        uploaded_by=ctx.user.id,
        created_at=utcnow(),
    )
    ctx.db.add(version)
    await ctx.db.flush()
    doc.current_version_id = version.id
    doc.updated_at = utcnow()
    await index(ctx.db, doc, version, data)
    await ctx.db.flush()
    await audit.record(
        ctx.db,
        "document.version_uploaded",
        target_type="document",
        target_id=doc.id,
        data={"version": number, "filename": name, "size": len(data), "sha256": digest},
    )
    if not doc.archived:
        members = [
            m
            for m in await ctx.db.scalars(select(Employee.membership_id).where(await _reach(ctx.db, doc)))
            if m
        ]
        await events.emit(
            ctx.db,
            "document.published",
            subject_type="document",
            subject_id=doc.id,
            data={
                "title": doc.title,
                "version": number,
                "requires_ack": doc.requires_ack,
                "membership_ids": members,
            },
        )
    await ctx.db.commit()
    return await get(ctx, doc.id)


async def index(db: AsyncSession, doc: Document, version: DocumentVersion, data: bytes) -> int:
    """Make the version's text searchable (replacing the document's older passages)."""
    await db.execute(delete(DocumentPassage).where(DocumentPassage.document_id == doc.id))
    pieces = text.passages(text.extract(version.filename, data))
    db.add_all(
        DocumentPassage(document_id=doc.id, version_id=version.id, ordinal=i, text=piece)
        for i, piece in enumerate(pieces)
    )
    return len(pieces)


async def _index_missing(ctx: Ctx) -> None:
    """Documents uploaded before search existed get indexed the first time anyone searches."""
    indexed = select(DocumentPassage.document_id).distinct()
    rows = (
        await ctx.db.execute(
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.id == Document.current_version_id)
            .where(Document.id.not_in(indexed), Document.archived.is_(False))
            .options(undefer(DocumentVersion.data))
            .limit(20)
        )
    ).all()
    for doc, version in rows:
        await index(ctx.db, doc, version, version.data)
    if rows:
        await ctx.db.commit()


async def search(ctx: Ctx, q: str, limit: int = 5) -> list[PassageOut]:
    """Passages that match `q`, from documents this person may read, best first."""
    ctx.require(access.READ)
    words = q.strip()
    if not words:
        return []
    await _index_missing(ctx)
    query = func.websearch_to_tsquery("simple", words)
    rank = func.ts_rank(DocumentPassage.search, query)
    rows = (
        await ctx.db.execute(
            select(DocumentPassage, Document, DocumentVersion.number)
            .join(Document, Document.id == DocumentPassage.document_id)
            .join(DocumentVersion, DocumentVersion.id == DocumentPassage.version_id)
            .where(await _visible(ctx), Document.archived.is_(False), DocumentPassage.search.op("@@")(query))
            .order_by(rank.desc(), DocumentPassage.ordinal)
            .limit(limit)
        )
    ).all()
    return [
        PassageOut(
            document_id=doc.id,
            title=doc.title,
            category=doc.category,
            version=number,
            text=passage.text,
            link=f"/app/documents?doc={doc.id}",
        )
        for passage, doc, number in rows
    ]


async def download(ctx: Ctx, document_id: uuid.UUID, version_id: uuid.UUID) -> tuple[bytes, str, str]:
    doc = await _document(ctx, document_id)
    row = (
        await ctx.db.execute(
            select(DocumentVersion.data, DocumentVersion.filename, DocumentVersion.content_type).where(
                DocumentVersion.id == version_id, DocumentVersion.document_id == doc.id
            )
        )
    ).first()
    if row is None:
        raise NotFound()
    return row[0], row[1], row[2]


async def acknowledge(ctx: Ctx, document_id: uuid.UUID) -> DocumentDetail:
    doc = await _document(ctx, document_id)
    if not doc.requires_ack or doc.current_version_id is None:
        raise Invalid("This document doesn't ask for acknowledgement.", code="no_ack_needed")
    await ctx.db.execute(
        insert(DocumentAck)
        .values(
            tenant_id=doc.tenant_id, version_id=doc.current_version_id, user_id=ctx.user.id, acked_at=utcnow()
        )
        .on_conflict_do_nothing()
    )
    await audit.record(
        ctx.db, "document.acknowledged", target_type="document", target_id=doc.id, data={"title": doc.title}
    )
    await events.emit(
        ctx.db,
        "document.acknowledged",
        subject_type="document",
        subject_id=doc.id,
        data={"document_id": doc.id, "title": doc.title, "version_id": doc.current_version_id},
    )
    await ctx.db.commit()
    return await get(ctx, doc.id)


async def acknowledgements(ctx: Ctx, document_id: uuid.UUID) -> AcksOut:
    if not ctx.can(access.MANAGE):
        raise Forbidden()
    doc = await _document(ctx, document_id)
    version = await ctx.db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    rows = (
        await ctx.db.execute(
            select(Employee.id, Employee.full_name, Department.name, DocumentAck.acked_at)
            .join(Membership, Membership.id == Employee.membership_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(
                DocumentAck,
                and_(
                    DocumentAck.version_id == doc.current_version_id,
                    DocumentAck.user_id == Membership.user_id,
                ),
            )
            .where(await _reach(ctx.db, doc))
            .order_by(DocumentAck.acked_at.is_(None).desc(), func.lower(Employee.full_name))
        )
    ).all()
    people = [AckPerson(employee_id=r[0], name=r[1], department=r[2], acked_at=r[3]) for r in rows]
    return AcksOut(
        version_number=version.number if version else None,
        total=len(people),
        acknowledged=sum(1 for p in people if p.acked_at),
        people=people,
    )
