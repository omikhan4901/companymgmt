"""The assistant over HTTP: status and settings, questions and conversations, the
capabilities it can call, and the operators' allowance settings."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, StringConstraints

from app.ai import actions, assistant, automations, brief, operator, workspace, writing
from app.ai.context import RequestContext, build_context
from app.ai.tools import tool_specs
from app.modules.platform.capabilities import invoke
from app.modules.platform.catalog import AI_USE
from app.modules.platform.deps import Ctx, allow, signed_in

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


@router.get("/status", response_model=workspace.AIStatusOut)
async def status(ctx: Ctx = Depends(allow(None))) -> workspace.AIStatusOut:
    return await workspace.status(ctx)


@router.put("/settings", response_model=workspace.AIStatusOut)
async def save_settings(
    body: workspace.AISettingsIn, ctx: Ctx = Depends(allow(None))
) -> workspace.AIStatusOut:
    return await workspace.save(ctx, body)


@router.post("/ask", response_model=assistant.AnswerOut)
async def ask(body: assistant.AskIn, ctx: Ctx = Depends(allow(AI_USE))) -> assistant.AnswerOut:
    return await assistant.ask(ctx, body)


@router.post("/brief", response_model=brief.BriefOut)
async def weekly_brief(ctx: Ctx = Depends(allow(AI_USE))) -> brief.BriefOut:
    return await brief.brief(ctx)


@router.post("/write", response_model=writing.WriteOut)
async def write(body: writing.WriteIn, ctx: Ctx = Depends(allow(AI_USE))) -> writing.WriteOut:
    """Draft, improve, shorten or translate text. Nothing is saved."""
    return await writing.write(ctx, body)


@router.post("/documents/{document_id}/summary", response_model=writing.WriteOut)
async def summarise(document_id: uuid.UUID, ctx: Ctx = Depends(allow(AI_USE))) -> writing.WriteOut:
    return await writing.summarise(ctx, document_id)


@router.post("/automations/draft", response_model=automations.DraftOut)
async def draft_automation(
    body: automations.DraftIn, ctx: Ctx = Depends(allow(AI_USE))
) -> automations.DraftOut:
    """An automation drafted from plain words, for the editor. Nothing is saved."""
    return await automations.draft(ctx, body)


@router.post("/actions/{action_id}/confirm", response_model=actions.ActionOut)
async def confirm_action(action_id: uuid.UUID, ctx: Ctx = Depends(allow(AI_USE))) -> actions.ActionOut:
    """Do what the assistant offered, as the person confirming it."""
    return await actions.confirm(ctx, action_id)


@router.post("/actions/{action_id}/cancel", response_model=actions.ActionOut)
async def cancel_action(action_id: uuid.UUID, ctx: Ctx = Depends(allow(AI_USE))) -> actions.ActionOut:
    return await actions.cancel(ctx, action_id)


@router.get("/conversations", response_model=list[assistant.ConversationOut])
async def conversations(ctx: Ctx = Depends(allow(AI_USE))) -> list[assistant.ConversationOut]:
    return await assistant.conversations(ctx)


@router.get("/conversations/{conversation_id}", response_model=assistant.ConversationOut)
async def conversation(
    conversation_id: uuid.UUID, ctx: Ctx = Depends(allow(AI_USE))
) -> assistant.ConversationOut:
    return await assistant.conversation(ctx, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def forget(conversation_id: uuid.UUID, ctx: Ctx = Depends(allow(AI_USE))) -> Response:
    await assistant.forget(ctx, conversation_id)
    return Response(status_code=204)


operator_router = APIRouter(prefix="/v1/operator", tags=["operator"])


@operator_router.get("/ai-allowances", response_model=list[operator.AllowanceOut])
async def allowances(ctx: Ctx = Depends(signed_in())) -> list[operator.AllowanceOut]:
    return await operator.allowances(ctx)


@operator_router.put("/ai-allowances", response_model=list[operator.AllowanceOut])
async def save_allowances(
    body: operator.AllowancesIn, ctx: Ctx = Depends(signed_in())
) -> list[operator.AllowanceOut]:
    return await operator.save_allowances(ctx, body)


class OperatorMe(BaseModel):
    operator: bool


@operator_router.get("/me", response_model=OperatorMe)
async def operator_me(ctx: Ctx = Depends(signed_in())) -> OperatorMe:
    return OperatorMe(operator=operator.is_operator(ctx))
