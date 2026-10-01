"""Capability endpoints: what the assistant will see and call (reads only until M7)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints

from app.ai.context import RequestContext, build_context
from app.ai.tools import tool_specs
from app.modules.platform.capabilities import invoke
from app.modules.platform.deps import Ctx, allow

router = APIRouter(prefix="/v1/ai", tags=["ai"])


@router.get("/context", response_model=RequestContext)
async def context(ctx: Ctx = Depends(allow(None))) -> RequestContext:
    return await build_context(ctx)


@router.get("/capabilities")
async def capabilities(ctx: Ctx = Depends(allow(None))) -> list[dict[str, Any]]:
    return tool_specs(ctx)


class InvokeIn(BaseModel):
    name: Annotated[str, StringConstraints(max_length=80, pattern=r"^[a-z_]+\.[a-z_]+$")]
    input: dict[str, Any] = Field(default_factory=dict)


@router.post("/capabilities/invoke")
async def run(body: InvokeIn, ctx: Ctx = Depends(allow(None))) -> Any:
    return await invoke(ctx, body.name, body.input)
