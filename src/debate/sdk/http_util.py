"""HTTP status and transport error mapping for provider SDKs."""

from __future__ import annotations

import httpx

from debate.sdk.errors import PermanentProviderError, TransientProviderError


def raise_for_response(response: httpx.Response) -> None:
    code = response.status_code
    detail = response.text[:240]
    if code == 429 or code >= 500:
        raise TransientProviderError(f"HTTP {code}: {detail}")
    if code >= 400:
        raise PermanentProviderError(f"HTTP {code}: {detail}")


def raise_for_transport(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise TransientProviderError(f"timeout: {exc}") from exc
    if isinstance(exc, httpx.HTTPStatusError):
        raise_for_response(exc.response)
    raise PermanentProviderError(str(exc)) from exc
