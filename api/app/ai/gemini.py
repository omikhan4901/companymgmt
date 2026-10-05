"""Gemini through its REST API (no SDK): chat with function calling, and embeddings.

Only plain HTTPS with an API key header. Tool names can't contain dots, so `leave.balances`
travels as `leave__balances`. Gemini accepts a subset of JSON Schema (OpenAPI style), so
schemas are simplified before sending: references inlined, "X or null" made nullable,
unsupported keywords dropped.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.ai.provider import AIUnavailable, Reply, Tool, ToolCall, Turn
from app.core.config import get_settings

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(45.0, connect=10.0)
KEEP = {
    "type",
    "description",
    "properties",
    "required",
    "items",
    "enum",
    "format",
    "nullable",
    "minimum",
    "maximum",
}
FORMATS = {"date-time", "enum", "int32", "int64", "float", "double"}


def wire_name(name: str) -> str:
    return name.replace(".", "__")


def real_name(name: str) -> str:
    return name.replace("__", ".")


def simplify(schema: Any, defs: dict[str, Any] | None = None, depth: int = 0) -> Any:
    """A JSON Schema reduced to what Gemini's function declarations understand."""
    if not isinstance(schema, dict) or depth > 12:
        return {"type": "string"}
    defs = {**(defs or {}), **schema.get("$defs", {})}
    if "$ref" in schema:
        target = defs.get(str(schema["$ref"]).split("/")[-1], {})
        return simplify(target, defs, depth + 1)
    if "anyOf" in schema or "oneOf" in schema:
        choices: list[Any] = list(schema.get("anyOf") or schema.get("oneOf") or [])
        options = [o for o in choices if isinstance(o, dict) and o.get("type") != "null"]
        merged: dict[str, Any] = simplify(options[0] if options else {"type": "string"}, defs, depth + 1)
        if len(options) < len(choices):
            merged["nullable"] = True
        if "description" in schema:
            merged["description"] = schema["description"]
        return merged
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in KEEP:
            continue
        if key == "properties":
            out[key] = {k: simplify(v, defs, depth + 1) for k, v in value.items()}
        elif key == "items":
            out[key] = simplify(value, defs, depth + 1)
        elif key == "format":
            if value in FORMATS:
                out[key] = value
        else:
            out[key] = value
    if "type" not in out:
        out["type"] = "object" if "properties" in out else "string"
    if out["type"] == "object" and not out.get("properties"):
        out.pop("required", None)
    return out


def _content(turn: Turn) -> dict[str, Any]:
    if turn.role == "tool":
        return {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": wire_name(turn.tool_name or ""),
                        "response": {"result": turn.tool_result},
                    }
                }
            ],
        }
    parts: list[dict[str, Any]] = []
    if turn.text:
        parts.append({"text": turn.text})
    for call in turn.tool_calls:
        parts.append({"functionCall": {"name": wire_name(call.name), "args": call.args}})
    return {"role": "model" if turn.role == "model" else "user", "parts": parts or [{"text": ""}]}


class Gemini:
    name = "gemini"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, key: str | None = None) -> None:
        # `transport` lets tests answer instead of Google; `key` is a workspace's own key.
        self.transport = transport
        settings = get_settings()
        self.key = key or settings.gemini_api_key.get_secret_value()
        self.model = settings.gemini_model
        self.embed_model = settings.gemini_embed_model
        self.base = settings.gemini_base_url.rstrip("/")

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base}/{path}", json=body, headers={"x-goog-api-key": self.key}
                )
        except httpx.HTTPError as exc:
            log.warning("gemini unreachable", extra={"error": type(exc).__name__})
            raise AIUnavailable() from exc
        if response.status_code == 429:
            raise AIUnavailable("The assistant is busy. Try again in a minute.")
        if response.status_code >= 400:
            log.warning("gemini error", extra={"status": response.status_code, "body": response.text[:500]})
            raise AIUnavailable()
        data: dict[str, Any] = response.json()
        return data

    async def generate(self, system: str, turns: list[Turn], tools: list[Tool]) -> Reply:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [_content(t) for t in turns],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
        if tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": wire_name(t.name),
                            "description": t.description,
                            "parameters": simplify(t.parameters),
                        }
                        for t in tools
                    ]
                }
            ]
        data = await self._post(f"models/{self.model}:generateContent", body)
        candidates = data.get("candidates") or []
        if not candidates:
            raise AIUnavailable("The assistant couldn't answer that. Try asking another way.")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        reply = Reply()
        texts = []
        for part in parts:
            if "text" in part:
                texts.append(part["text"])
            if "functionCall" in part:
                call = part["functionCall"]
                reply.tool_calls.append(
                    ToolCall(name=real_name(call.get("name", "")), args=call.get("args") or {})
                )
        reply.text = "".join(texts).strip()
        usage = data.get("usageMetadata") or {}
        reply.tokens_in = int(usage.get("promptTokenCount") or 0)
        reply.tokens_out = int(usage.get("candidatesTokenCount") or 0)
        return reply

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = f"models/{self.embed_model}"
        body = {"requests": [{"model": model, "content": {"parts": [{"text": t[:8000]}]}} for t in texts]}
        data = await self._post(f"{model}:batchEmbedContents", body)
        return [list(map(float, e.get("values") or [])) for e in data.get("embeddings") or []]
