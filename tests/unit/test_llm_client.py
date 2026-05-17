"""Unit tests for LLMClient (respx + httpx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from debate.sdk.llm_client import LLMClient
from debate.shared.budget import PermanentProviderError, TransientProviderError

_URL = "https://api.openai.com/v1/chat/completions"
_OK = {
    "choices": [{"message": {"content": "Hello debate."}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 8},
}


@pytest.fixture
def http() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(5.0))


@pytest.fixture
def llm(http: httpx.Client) -> LLMClient:
    return LLMClient("gpt-4o-mini", 0.7, http)


@pytest.mark.unit
@respx.mock
def test_chat_happy_path(llm: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_OK))
    result = llm.chat([{"role": "user", "content": "hi"}], max_tokens=50)
    assert result.text == "Hello debate."
    assert result.tokens_in == 12
    assert result.tokens_out == 8
    assert result.model == "gpt-4o-mini"
    assert "sk-test" not in repr(llm)


@pytest.mark.unit
@respx.mock
def test_chat_429_is_transient(llm: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    respx.post(_URL).mock(return_value=httpx.Response(429, text="rate limited"))
    with pytest.raises(TransientProviderError):
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=10)


@pytest.mark.unit
@respx.mock
def test_chat_400_is_permanent(llm: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    respx.post(_URL).mock(return_value=httpx.Response(400, text="bad request"))
    with pytest.raises(PermanentProviderError):
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=10)


@pytest.mark.unit
@respx.mock
def test_chat_timeout_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")

    def _timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=_request)

    respx.post(_URL).mock(side_effect=_timeout)
    client = httpx.Client(timeout=httpx.Timeout(0.01))
    llm = LLMClient("gpt-4o-mini", 0.7, client)
    with pytest.raises(TransientProviderError):
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=10)


@pytest.mark.unit
@respx.mock
def test_malformed_json_is_permanent(llm: LLMClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"choices": []}))
    with pytest.raises(PermanentProviderError):
        llm.chat([{"role": "user", "content": "hi"}], max_tokens=10)
