"""Protocols for skill factories (shared by ``skills`` modules)."""

from __future__ import annotations

from typing import Any, Protocol

from debate.sdk.llm_client import ChatResult
from debate.sdk.payloads import SearchHit


class LLMClientProto(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult: ...


class SearchClientProto(Protocol):
    def query(self, text: str, k: int) -> list[SearchHit]: ...
