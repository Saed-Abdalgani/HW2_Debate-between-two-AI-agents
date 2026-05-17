"""Unit tests for SearchClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from debate.sdk.search_client import SearchClient, _sanitize, _truncate
from debate.shared.budget import PermanentProviderError

_URL = "https://api.tavily.com/search"


@pytest.fixture
def http() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(5.0))


@pytest.fixture
def search(http: httpx.Client) -> SearchClient:
    return SearchClient("tavily", http, snippet_max_chars=40)


@pytest.mark.unit
def test_truncate_and_sanitize() -> None:
    assert _truncate("abcdef", 4) == "abcd"
    assert "\x07" not in _sanitize("a\x07b")


@pytest.mark.unit
@respx.mock
def test_query_happy_path(search: SearchClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_API_KEY", "tvly-testkey1234567890")
    respx.post(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Title\x07",
                        "url": "https://example.com",
                        "content": "x" * 80,
                    }
                ]
            },
        )
    )
    hits = search.query("climate policy", 3)
    assert len(hits) == 1
    assert hits[0].title == "Title"
    assert len(hits[0].snippet) == 40
    assert "SEARCH" not in repr(search)


@pytest.mark.unit
@respx.mock
def test_malformed_response(search: SearchClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_API_KEY", "tvly-testkey1234567890")
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"oops": True}))
    with pytest.raises(PermanentProviderError):
        search.query("q", 1)


@pytest.mark.unit
@respx.mock
def test_unsupported_provider(http: httpx.Client) -> None:
    client = SearchClient("bing", http, snippet_max_chars=100)
    with pytest.raises(PermanentProviderError, match="unsupported"):
        client.query("q", 1)
