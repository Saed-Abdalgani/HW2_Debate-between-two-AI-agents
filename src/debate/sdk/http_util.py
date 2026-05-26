"""HTTP status and transport error mapping for provider SDKs."""

from __future__ import annotations

import re

import httpx

from debate.sdk.errors import PermanentProviderError, TransientProviderError

# Groq/OpenAI-style bodies can say "try again in 16.55s"; cap to avoid hangs.
_MAX_RETRY_AFTER_SEC = 120.0


def _retry_after_from_response(response: httpx.Response) -> float | None:
    """Best-effort parse for HTTP 429 (``Retry-After`` or JSON message)."""
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return min(float(raw), _MAX_RETRY_AFTER_SEC)
        except ValueError:
            pass
    text = response.text
    m = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*s", text, re.IGNORECASE)
    if m:
        return min(float(m.group(1)), _MAX_RETRY_AFTER_SEC)
    return None


def raise_for_response(response: httpx.Response) -> None:
    code = response.status_code
    detail = response.text[:240]
    if code == 429 or code >= 500:
        ra = _retry_after_from_response(response) if code == 429 else None
        raise TransientProviderError(f"HTTP {code}: {detail}", retry_after_sec=ra)
    if code >= 400:
        raise PermanentProviderError(f"HTTP {code}: {detail}")


def raise_for_transport(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise TransientProviderError(f"timeout: {exc}") from exc
    if isinstance(exc, httpx.HTTPStatusError):
        raise_for_response(exc.response)
    raise PermanentProviderError(str(exc)) from exc
