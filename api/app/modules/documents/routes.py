"""Documents API: the library, versions (uploaded as the raw request body), downloads
and acknowledgements."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import check_if_match, read_body, set_etag
from app.core.middleware import allow_upload
from app.modules.documents import access, files, service
from app.modules.documents.schemas import AcksOut, DocumentDetail, DocumentIn, DocumentOut, DocumentPatch
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/documents", tags=["documents"])
MODULE = "documents"
# A little headroom so a slightly-too-big file gets the clear "up to 10 MB" message.
allow_upload(r"/v1/documents/[0-9a-fA-F-]{36}/versions", files.MAX_SIZE + 64 * 1024)
Read = Depends(allow(access.READ, module=MODULE))
Manage = Depends(allow(access.MANAGE, module=MODULE))


@router.get("", response_model=list[DocumentOut])
async def library(ctx: Ctx = Read, archived: bool = False) -> list[DocumentOut]:
    return await service.list_documents(ctx, archived=archived)


@router.get("/to-acknowledge", response_model=list[DocumentOut])
async def to_acknowledge(ctx: Ctx = Read) -> list[DocumentOut]:
    return await service.list_documents(ctx, to_acknowledge=True)


@router.post("", response_model=DocumentDetail, status_code=201)
async def create(body: DocumentIn, ctx: Ctx = Manage) -> DocumentDetail:
    return await service.create(ctx, body)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get(document_id: uuid.UUID, response: Response, ctx: Ctx = Read) -> DocumentDetail:
    doc = await service.get(ctx, document_id)
    set_etag(response, doc.version)
    return doc


@router.patch("/{document_id}", response_model=DocumentDetail)
async def update(
    document_id: uuid.UUID, body: DocumentPatch, request: Request, response: Response, ctx: Ctx = Manage
) -> DocumentDetail:
    check_if_match(request, (await service.get(ctx, document_id)).version)
    doc = await service.update(ctx, document_id, body)
    set_etag(response, doc.version)
    return doc


@router.post("/{document_id}/versions", response_model=DocumentDetail, status_code=201)
async def upload(
    document_id: uuid.UUID,
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=300)],
    note: Annotated[str | None, Query(max_length=500)] = None,
    ctx: Ctx = Manage,
) -> DocumentDetail:
    """Body: the file itself."""
    data = await read_body(
        request, files.MAX_SIZE, message="Files can be up to 10 MB.", code="file_too_large"
    )
    return await service.upload(ctx, document_id, filename, note, data)


@router.get("/{document_id}/versions/{version_id}/file")
async def download(document_id: uuid.UUID, version_id: uuid.UUID, ctx: Ctx = Read) -> Response:
    data, filename, content_type = await service.download(ctx, document_id, version_id)
    ascii_name = filename.encode("ascii", "replace").decode().replace('"', "'")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            # Always a download, never shown in the browser as a page.
            "content-disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            ),
            "x-content-type-options": "nosniff",
            "cache-control": "private, no-store",
        },
    )


@router.post("/{document_id}/acknowledge", response_model=DocumentDetail)
async def acknowledge(document_id: uuid.UUID, ctx: Ctx = Read) -> DocumentDetail:
    return await service.acknowledge(ctx, document_id)


@router.get("/{document_id}/acknowledgements", response_model=AcksOut)
async def acknowledgements(document_id: uuid.UUID, ctx: Ctx = Manage) -> AcksOut:
    return await service.acknowledgements(ctx, document_id)
