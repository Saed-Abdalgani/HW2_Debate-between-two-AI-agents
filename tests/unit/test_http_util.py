"""Unit tests for HTTP error mapping (429 retry hints)."""

from __future__ import annotations

import httpx
import pytest

from debate.sdk.errors import TransientProviderError
from debate.sdk.http_util import raise_for_response


@pytest.mark.unit
def test_429_retry_after_header() -> None:
    r = httpx.Response(429, headers={"retry-after": "12"}, text="slow down")
    with pytest.raises(TransientProviderError) as ei:
        raise_for_response(r)
    assert ei.value.retry_after_sec == pytest.approx(12.0)


@pytest.mark.unit
def test_429_groq_try_again_in_message() -> None:
    body = '{"error":{"message":"Please try again in 16.55s"}}'
    r = httpx.Response(429, text=body)
    with pytest.raises(TransientProviderError) as ei:
        raise_for_response(r)
    assert ei.value.retry_after_sec == pytest.approx(16.55)


@pytest.mark.unit
def test_429_retry_after_caps_huge_header() -> None:
    r = httpx.Response(429, headers={"retry-after": "9999"}, text="x")
    with pytest.raises(TransientProviderError) as ei:
        raise_for_response(r)
    assert ei.value.retry_after_sec == pytest.approx(120.0)
