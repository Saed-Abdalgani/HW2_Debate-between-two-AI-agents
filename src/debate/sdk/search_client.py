"""Web search client — Tavily provider (P4)."""

from __future__ import annotations

import re

import httpx

from debate.sdk.errors import PermanentProviderError
from debate.sdk.http_util import raise_for_response, raise_for_transport
from debate.sdk.payloads import SearchHit
from debate.shared.secrets import get_key

_TAVILY_URL = "https://api.tavily.com/search"
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", text)
    return "".join(ch for ch in cleaned if ch.isprintable() or ch in "\n\t")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


class SearchClient:
    """Provider-specific search; Judge proxies calls for children."""

    def __init__(
        self,
        provider: str,
        http: httpx.Client,
        *,
        snippet_max_chars: int,
    ) -> None:
        self.provider = provider
        self._http = http
        self._snippet_max_chars = snippet_max_chars

    def __repr__(self) -> str:
        return f"SearchClient(provider={self.provider!r})"

    def query(self, text: str, k: int) -> list[SearchHit]:
        if self.provider == "tavily":
            return self._tavily(text, k)
        raise PermanentProviderError(f"unsupported search provider: {self.provider}")

    def _tavily(self, text: str, k: int) -> list[SearchHit]:
        body = {
            "api_key": get_key("SEARCH_API_KEY"),
            "query": text,
            "max_results": k,
        }
        try:
            response = self._http.post(_TAVILY_URL, json=body)
        except httpx.HTTPError as exc:
            raise_for_transport(exc)
        raise_for_response(response)
        return self._parse_tavily(response.json())

    def _parse_tavily(self, payload: object) -> list[SearchHit]:
        if not isinstance(payload, dict):
            raise PermanentProviderError("malformed search response")
        raw = payload.get("results")
        if not isinstance(raw, list):
            raise PermanentProviderError("malformed search response: missing results")
        hits: list[SearchHit] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = _sanitize(str(item.get("title", "")))
            url = _sanitize(str(item.get("url", "")))
            snippet = _truncate(
                _sanitize(str(item.get("content", item.get("snippet", "")))),
                self._snippet_max_chars,
            )
            hits.append(SearchHit(title=title, url=url, snippet=snippet))
        return hits
