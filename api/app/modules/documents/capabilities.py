"""Document capabilities (see platform/capabilities.py). File contents reach the
assistant only as passages found by `documents.search`, from documents the person may read."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.documents import access, service
from app.modules.documents.schemas import DocumentOut, PassageOut
from app.modules.platform.capabilities import NoInput, capability
from app.modules.platform.deps import Ctx

MODULE = "documents"


class LibraryIn(BaseModel):
    archived: bool = False


@capability(
    "documents.library",
    "Documents and policies you can read, with whether you've acknowledged them.",
    input=LibraryIn,
    output=list[DocumentOut],
    permission=access.READ,
    module=MODULE,
    route="GET /v1/documents",
)
async def library(ctx: Ctx, data: LibraryIn) -> list[DocumentOut]:
    return await service.list_documents(ctx, archived=data.archived)


@capability(
    "documents.to_acknowledge",
    "Policies waiting for you to read and acknowledge.",
    output=list[DocumentOut],
    permission=access.READ,
    module=MODULE,
    route="GET /v1/documents/to-acknowledge",
)
async def to_acknowledge(ctx: Ctx, _: NoInput) -> list[DocumentOut]:
    return await service.list_documents(ctx, to_acknowledge=True)


class SearchIn(BaseModel):
    q: str = Field(min_length=1, max_length=300, description="Words to look for, e.g. 'work from home'")
    limit: int = Field(default=5, ge=1, le=20)


@capability(
    "documents.search",
    "Passages from the policies and documents you can read that match some words, with "
    "the document's title and version. Use it to answer questions about company policies.",
    input=SearchIn,
    output=list[PassageOut],
    permission=access.READ,
    module=MODULE,
    route="GET /v1/documents/search",
)
async def search(ctx: Ctx, data: SearchIn) -> list[PassageOut]:
    return await service.search(ctx, data.q, data.limit)
