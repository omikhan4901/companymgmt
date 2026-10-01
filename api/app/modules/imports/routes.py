"""Spreadsheet import: preview a file, import it, or download a template to fill in."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.http import read_body
from app.core.middleware import allow_upload
from app.modules.imports import parse, service
from app.modules.imports.schemas import ImportOut
from app.modules.people.access import PEOPLE_MANAGE
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/people/import", tags=["people"])
Manage = Depends(allow(PEOPLE_MANAGE, module="people"))

allow_upload(r"/v1/people/import", parse.MAX_SIZE + 64 * 1024)


@router.post("", response_model=ImportOut)
async def import_people(
    request: Request, commit: Annotated[bool, Query()] = False, ctx: Ctx = Manage
) -> ImportOut:
    """Body: the CSV file itself. Without `commit`, nothing is saved."""
    data = await read_body(
        request, parse.MAX_SIZE, message="The file can be up to 2 MB.", code="file_too_large"
    )
    if commit:
        return await service.run(ctx, data)
    return await service.preview(ctx, data)


@router.get("/template", response_class=Response)
async def template(lang: Literal["en", "bn"] = "en", ctx: Ctx = Manage) -> Response:
    body = await service.template(ctx, lang)
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="people-import.csv"'},
    )
