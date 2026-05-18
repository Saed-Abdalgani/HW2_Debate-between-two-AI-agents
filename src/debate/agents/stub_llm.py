"""Test-only LLM stubs — activated via ``DEBATE_STUB_LLM`` env (integration tests)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from debate.sdk.llm_client import ChatResult

_TOOL = "TOOL:search:"


@dataclass
class EchoStubLLM:
    """Echoes the last user message — deterministic integration replies."""

    model: str = "gpt-4o-mini"

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user = str(msg.get("content", ""))
                break
        text = f"echo:{user[:120]}"
        return ChatResult(text=text, tokens_in=4, tokens_out=len(text) // 4 + 1, model=self.model)


@dataclass
class ToolStormStubLLM:
    """Returns three TOOL lines then a final argument (tool-cap tests)."""

    model: str = "gpt-4o-mini"
    _calls: int = field(default=0, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        self._calls += 1
        text = f"{_TOOL}query{self._calls}" if self._calls <= 3 else "Final argument with evidence."
        return ChatResult(text=text, tokens_in=3, tokens_out=8, model=self.model)


def stub_from_env(name: str | None) -> EchoStubLLM | ToolStormStubLLM | None:
    if name == "echo":
        return EchoStubLLM()
    if name in {"tool_storm", "tool_loop"}:
        return ToolStormStubLLM()
    return None
