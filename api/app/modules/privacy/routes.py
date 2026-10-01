"""Data export endpoints. Both need a recent sign-in."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.core.errors import Invalid
from app.modules.platform.deps import Ctx, allow
from app.modules.platform.routes_auth import require_recent_auth
from app.modules.privacy import access, importer, service

router = APIRouter(prefix="/v1/privacy", tags=["privacy"])


def _file(body: bytes, filename: str, media_type: str) -> Response:
    return Response(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get("/workspace-export")
async def workspace_export(ctx: Ctx = Depends(allow(access.WORKSPACE_EXPORT))) -> Response:
    require_recent_auth(ctx)
    body, filename = await service.workspace_export(ctx)
    return _file(body, filename, "application/zip")


@router.get("/my-data")
async def my_data(ctx: Ctx = Depends(allow(None))) -> Response:
    require_recent_auth(ctx)
    body, filename = await service.my_data(ctx)
    return _file(body, filename, "application/json")


async def _upload(request: Request) -> bytes:
    """The request body, refused as soon as it passes the size limit."""
    if int(request.headers.get("content-length") or 0) > importer.MAX_UPLOAD:
        raise Invalid("The file is too large.", code="import_too_large")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > importer.MAX_UPLOAD:
            raise Invalid("The file is too large.", code="import_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/workspace-import")
async def workspace_import(
    request: Request, ctx: Ctx = Depends(allow(access.WORKSPACE_IMPORT))
) -> dict[str, dict[str, int]]:
    """Body: the export ZIP itself (Content-Type: application/zip)."""
    require_recent_auth(ctx)
    return {"imported": await importer.import_workspace(ctx, await _upload(request))}
