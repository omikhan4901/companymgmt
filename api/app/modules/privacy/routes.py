"""Data export endpoints. Both need a recent sign-in."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.modules.platform.deps import Ctx, allow
from app.modules.platform.routes_auth import require_recent_auth
from app.modules.privacy import access, service

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
