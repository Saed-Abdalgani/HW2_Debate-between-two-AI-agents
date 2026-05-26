"""Stub LLM clients: echo, transient errors, rate limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from debate.sdk.errors import TransientProviderError
from debate.sdk.llm_client import ChatResult


@dataclass
class EchoStubLLM:
    """Echoes the last user message — deterministic integration replies."""

    model: str = "gpt-4o-mini"
    latency_sec: float = 0.0

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
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
class ErrorStubLLM:
    """Raises TransientProviderError on configurable call numbers."""

    model: str = "gpt-4o-mini"
    fail_on_calls: set[int] = field(default_factory=lambda: {1})
    _calls: int = field(default=0, init=False)

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        self._calls += 1
        if self._calls in self.fail_on_calls:
            raise TransientProviderError(f"simulated failure on call {self._calls}")
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

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        self._calls += 1
        if self._calls <= self.rate_limit_count:
            raise TransientProviderError("rate limited")
        return ChatResult(
            text="success after rate limit",
            tokens_in=4,
            tokens_out=8,
            model=self.model,
        )
