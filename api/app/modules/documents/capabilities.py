"""Document capabilities (see platform/capabilities.py). Metadata only: file contents
reach the assistant later, through permission-aware search (M6)."""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.documents import access, service
from app.modules.documents.schemas import DocumentOut
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
