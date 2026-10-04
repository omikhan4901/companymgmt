"""A scripted, deterministic stand-in for a language model (tests and local demos).

With a script, it returns the scripted replies in order. Without one it behaves like a
cautious assistant: for a question it calls the first offered tool whose name matches a
keyword in the question, then answers from the tool results, citing them as [1], [2]….
Embeddings are bag-of-words hashes, so similar words give similar vectors.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from app.ai.provider import Reply, Tool, ToolCall, Turn

KEYWORDS = (
    ("policy", "documents.search"),
    ("handbook", "documents.search"),
    ("document", "documents.search"),
    ("leave", "leave.balances"),
    ("away", "leave.calendar"),
    ("task", "tasks.my_work"),
    ("work", "tasks.my_work"),
    ("approv", "approvals.pending"),
    ("report", "reports.overview"),
    ("attendance", "reports.overview"),
    ("who", "people.search"),
    ("people", "people.search"),
)
DIMENSIONS = 64


class FakeModel:
    name = "fake"

    def __init__(self, script: list[Reply] | None = None) -> None:
        self.script = list(script or [])
        self.calls: list[tuple[str, list[Turn], list[Tool]]] = []

    async def generate(self, system: str, turns: list[Turn], tools: list[Tool]) -> Reply:
        self.calls.append((system, list(turns), list(tools)))
        if self.script:
            return self.script.pop(0)
        last = turns[-1]
        tokens = sum(len((t.text or "") + json.dumps(t.tool_result, default=str)) for t in turns) // 4
        if last.role == "tool":
            results = [t for t in turns if t.role == "tool"]
            lines = [
                f"{t.tool_name}: {json.dumps(t.tool_result, default=str)[:300]} [{i}]"
                for i, t in enumerate(results, 1)
            ]
            return Reply(text="Here's what I found.\n" + "\n".join(lines), tokens_in=tokens, tokens_out=40)
        question = (last.text or "").lower()
        offered = {t.name for t in tools}
        for word, tool in KEYWORDS:
            if word in question and tool in offered:
                args: dict[str, Any] = {"q": _keywords(question)} if tool == "documents.search" else {}
                return Reply(tool_calls=[ToolCall(tool, args)], tokens_in=tokens, tokens_out=10)
        return Reply(text="I can't find that in your workspace.", tokens_in=tokens, tokens_out=10)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vector = [0.0] * DIMENSIONS
            for word in re.findall(r"\w+", text.lower()):
                slot = int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIMENSIONS
                vector[slot] += 1.0
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            out.append([v / norm for v in vector])
        return out


STOP = {
    "what",
    "is",
    "our",
    "the",
    "a",
    "an",
    "about",
    "policy",
    "on",
    "do",
    "we",
    "have",
    "how",
    "can",
    "i",
    "my",
}


def _keywords(question: str) -> str:
    words = [w for w in re.findall(r"\w+", question.lower()) if w not in STOP]
    return " or ".join(words[:5]) or question
