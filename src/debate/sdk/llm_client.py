"""OpenAI-compatible chat-completions client (P4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from debate.sdk.http_util import raise_for_response, raise_for_transport
from debate.shared.secrets import get_env, get_key

_DEFAULT_BASE = "https://api.openai.com/v1"


def resolve_llm_base_url() -> str:
    """Return OpenAI-compatible API root (no trailing slash); default is official OpenAI."""
    raw = get_env("LLM_BASE_URL")
    if raw is None or not raw.strip():
        return _DEFAULT_BASE
    return raw.strip().rstrip("/")


@dataclass(frozen=True)
class ChatResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str


class LLMClient:
    """Thin wrapper; USD pricing is applied by the Gatekeeper, not here."""

    def __init__(
        self,
        model: str,
        temperature: float,
        http: httpx.Client,
        *,
        base_url: str = _DEFAULT_BASE,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self._http = http
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._extra_headers = dict(extra_headers or {})

    def __repr__(self) -> str:
        return f"LLMClient(model={self.model!r}, temperature={self.temperature})"

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResult:
        headers = {
            "Authorization": f"Bearer {get_key('LLM_API_KEY')}",
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format
        try:
            response = self._http.post(self._url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise_for_transport(exc)
        raise_for_response(response)
        payload = response.json()
        return self._parse(payload)

    def _parse(self, payload: dict[str, Any]) -> ChatResult:
        try:
            text = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
            tin = int(usage.get("prompt_tokens", 0))
            tout = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            from debate.sdk.errors import PermanentProviderError

            raise PermanentProviderError("malformed chat completion response") from exc
        if not isinstance(text, str):
            text = str(text)
        return ChatResult(text=text, tokens_in=tin, tokens_out=tout, model=self.model)
