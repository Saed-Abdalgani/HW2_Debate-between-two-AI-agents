"""Test-only LLM stubs — activated via ``DEBATE_STUB_LLM`` env var.
Includes echo stub, tool-storm stub, error-injection stub,
rate-limit simulation, and call-tracking wrapper for test assertions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from debate.sdk.llm_client import ChatResult
from debate.sdk.errors import TransientProviderError

_TOOL = "TOOL:search:"


@dataclass
class EchoStubLLM:
    """Echoes the last user message — deterministic integration replies."""

    model: str = "gpt-4o-mini"
    latency_sec: float = 0.0

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        if self.latency_sec > 0:
            time.sleep(self.latency_sec)
        user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user = str(msg.get("content", ""))
                break
        text = f"echo:{user[:120]}"
        return ChatResult(
            text=text,
            tokens_in=4,
            tokens_out=len(text) // 4 + 1,
            model=self.model,
        )


@dataclass
class ToolStormStubLLM:
    """Returns TOOL lines then a final argument (tool-cap tests)."""

    model: str = "gpt-4o-mini"
    storm_count: int = 3
    _calls: int = field(default=0, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        self._calls += 1
        if self._calls <= self.storm_count:
            text = f"{_TOOL}query{self._calls}"
        else:
            text = "Final argument with evidence."
        return ChatResult(text=text, tokens_in=3, tokens_out=8, model=self.model)


@dataclass
class ErrorStubLLM:
    """Raises TransientProviderError on configurable call numbers."""

    model: str = "gpt-4o-mini"
    fail_on_calls: set[int] = field(default_factory=lambda: {1})
    _calls: int = field(default=0, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        self._calls += 1
        if self._calls in self.fail_on_calls:
            raise TransientProviderError(
                f"simulated failure on call {self._calls}",
                # pyrefly: ignore [unexpected-keyword]
                provider_status=500,
            )
        return ChatResult(
            text="recovered reply",
            tokens_in=4,
            tokens_out=6,
            model=self.model,
        )


@dataclass
class RateLimitStubLLM:
    """Simulates 429 rate-limit errors for N calls, then succeeds."""

    model: str = "gpt-4o-mini"
    rate_limit_count: int = 3
    _calls: int = field(default=0, init=False)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        self._calls += 1
        if self._calls <= self.rate_limit_count:
            raise TransientProviderError(
                "rate limited",
                # pyrefly: ignore [unexpected-keyword]
                provider_status=429,
            )
        return ChatResult(
            text="success after rate limit",
            tokens_in=4,
            tokens_out=8,
            model=self.model,
        )


@dataclass
class CountingStubLLM:
    """Wraps any LLM stub to count calls per role for assertions."""

    inner: Any = field(default_factory=EchoStubLLM)
    call_counts: dict[str, int] = field(default_factory=dict)

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
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
        return self.inner.chat(messages, max_tokens)


def stub_from_env(
    name: str | None,
) -> EchoStubLLM | ToolStormStubLLM | ErrorStubLLM | None:
    """Create a stub LLM from the DEBATE_STUB_LLM env var value."""
    if name == "echo":
        return EchoStubLLM()
    if name in {"tool_storm", "tool_loop"}:
        return ToolStormStubLLM()
    if name == "error":
        return ErrorStubLLM()
    return None
