"""The provider port: what the assistant needs from a language model, and nothing more.

A model takes a system prompt, the conversation so far and the tools it may call, and
returns text and/or tool calls. It can also turn text into vectors for search. Gemini
(`gemini.py`) is the real one; `fake.py` is a scripted stand-in for tests. Which one runs
is decided by settings: setting GEMINI_API_KEY is enough to switch AI on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.core.config import get_settings


class AIUnavailable(Exception):
    """No model is configured, or the provider failed. The message is safe to show."""

    def __init__(
        self, message: str = "The assistant isn't available right now. Try again in a minute."
    ) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Turn:
    """One step of a conversation: a person's words, the model's reply, or a tool result."""

    role: Literal["user", "model", "tool"]
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str | None = None
    tool_result: Any = None


@dataclass
class Tool:
    name: str
    description: str
    # JSON Schema of the arguments.
    parameters: dict[str, Any]


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0


class Model(Protocol):
    name: str

    async def generate(self, system: str, turns: list[Turn], tools: list[Tool]) -> Reply: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


_override: Model | None = None
_cached: tuple[str, Model] | None = None


def use_model(model: Model | None) -> None:
    """Tests: answer with this model (None goes back to the configured one)."""
    global _override
    _override = model


def provider_name() -> str:
    if _override is not None:
        return _override.name
    return get_settings().ai_provider_name


def available() -> bool:
    return bool(provider_name())


def get_model() -> Model:
    """The configured model, or AIUnavailable when there's none."""
    global _cached
    if _override is not None:
        return _override
    name = get_settings().ai_provider_name
    if not name:
        raise AIUnavailable("The assistant isn't set up on this server yet.")
    if _cached is None or _cached[0] != name:
        if name == "gemini":
            from app.ai.gemini import Gemini

            _cached = (name, Gemini())
        else:
            from app.ai.fake import FakeModel

            _cached = (name, FakeModel())
    return _cached[1]
