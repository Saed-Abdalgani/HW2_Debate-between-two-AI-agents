"""Stub LLM clients: tool storms, per-role counting, fact-check simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from debate.agents.stub_llm_basic import EchoStubLLM
from debate.sdk.llm_client import ChatResult

_TOOL = "TOOL:search:"


@dataclass
class ToolStormStubLLM:
    """Returns TOOL lines then a final argument (tool-cap tests)."""

    model: str = "gpt-4o-mini"
    storm_count: int = 3
    _calls: int = field(default=0, init=False)

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        self._calls += 1
        if self._calls <= self.storm_count:
            text = f"{_TOOL}query{self._calls}"
        else:
            text = "Final argument with evidence."
        return ChatResult(text=text, tokens_in=3, tokens_out=8, model=self.model)


@dataclass
class CountingStubLLM:
    """Wraps any LLM stub to count calls per role for assertions."""

    inner: Any = field(default_factory=EchoStubLLM)
    call_counts: dict[str, int] = field(default_factory=dict)

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        role = "unknown"
        for msg in messages:
            if msg.get("role") == "system":
                content = str(msg.get("content", ""))
                if "pro" in content.lower():
                    role = "pro"
                elif "con" in content.lower():
                    role = "con"
                break
        self.call_counts[role] = self.call_counts.get(role, 0) + 1
        return self.inner.chat(messages, max_tokens, response_format=response_format)


@dataclass
class FactCheckStubLLM:
    """Con-side test double: searches once when a known false claim appears."""

    model: str = "gpt-4o-mini"
    marker: str = "London is the capital of France"

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        blob = "\n".join(str(m.get("content", "")) for m in messages)
        tool_rounds = sum(1 for m in messages if m.get("role") == "assistant")
        if self.marker in blob and tool_rounds == 0:
            return ChatResult(
                text=f"{_TOOL}capital city of France verified",
                tokens_in=4,
                tokens_out=8,
                model=self.model,
            )
        if tool_rounds >= 1 and "Search results:" in blob:
            return ChatResult(
                text=(
                    "Authoritative references list Paris as the capital of France, "
                    "so the opponent's claim is disproven and cannot support their case."
                ),
                tokens_in=6,
                tokens_out=24,
                model=self.model,
            )
        return ChatResult(
            text=(
                "Structured counter-position opposing the motion with clear premises "
                "and anticipated objections from the other side."
            ),
            tokens_in=4,
            tokens_out=20,
            model=self.model,
        )
