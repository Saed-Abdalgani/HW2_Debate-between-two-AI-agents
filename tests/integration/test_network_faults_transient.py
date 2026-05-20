"""Integration — chaos engineering with network and provider faults (P9.4) - Transient."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
import respx

from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        },
    )


@pytest.mark.integration
@respx.mock
def test_network_latency_transient(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulated latency: httpx.MockTransport that sleeps cfg.http_timeout_sec + 1
    # -> assert SDK raises TransientProviderError
    # -> Gatekeeper retries -> succeeds on second attempt.
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)

    cfg = load_config().model_copy(
        update={
            "rounds": 1,
            "http_timeout_sec": 0.1,
            "retry_initial_delay_sec": 0.1,
            "max_retries": 2,
        }
    )
    run = tmp_path / "runs" / "full"
    logger = Logger(run, root=tmp_path)

    attempts = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            time.sleep(0.2)  # Longer than timeout
            raise httpx.ReadTimeout("read timed out", request=request)
        return _ok_response(
            json.dumps(
                {"winner": "pro", "reasons": ["A", "B", "C"], "scores": {"pro": 100, "con": 90}}
            )
        )

    respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=side_effect)

    # Let's test just Gatekeeper execute
    gk = Gatekeeper(cfg, logger=logger, run_dir=run)
    from debate.sdk.llm_client import LLMClient

    llm = LLMClient(cfg.judge_model, cfg.temperature, httpx.Client(timeout=cfg.http_timeout_sec))

    result = gk.execute(
        lambda: llm.chat([{"role": "user", "content": "hi"}], 10),
        estimate=gk.build_estimate([{"role": "user", "content": "hi"}], cfg.judge_model),
        role="judge",
        turn_id=1,
        model=cfg.judge_model,
    )

    assert attempts == 2
    assert json.loads(result.text)["winner"] == "pro"


@pytest.mark.integration
@respx.mock
def test_rate_limit_backoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulated rate-limit: provider returns 429 thrice then 200;
    # assert exponential back-off honoured.
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")

    cfg = load_config().model_copy(
        update={
            "rounds": 1,
            "retry_initial_delay_sec": 0.1,
            "retry_jitter_sec": 0.0,  # Zero jitter for timing predictability
            "max_retries": 4,
        }
    )
    run = tmp_path / "runs" / "full"
    logger = Logger(run, root=tmp_path)

    attempts = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= 3:
            return httpx.Response(429, text="Rate limited")
        return _ok_response("Success")

    respx.post("https://api.openai.com/v1/chat/completions").mock(side_effect=side_effect)

    gk = Gatekeeper(cfg, logger=logger, run_dir=run)
    from debate.sdk.llm_client import LLMClient

    llm = LLMClient(cfg.judge_model, cfg.temperature, httpx.Client(timeout=cfg.http_timeout_sec))

    t0 = time.monotonic()
    result = gk.execute(
        lambda: llm.chat([{"role": "user", "content": "hi"}], 10),
        estimate=gk.build_estimate([{"role": "user", "content": "hi"}], cfg.judge_model),
        role="judge",
        turn_id=1,
        model=cfg.judge_model,
    )
    t1 = time.monotonic()

    assert attempts == 4
    assert result.text == "Success"

    # Backoffs:
    # attempt 0 (fails) -> wait 0.1 * 1 = 0.1
    # attempt 1 (fails) -> wait 0.1 * 2 = 0.2
    # attempt 2 (fails) -> wait 0.1 * 4 = 0.4
    # Total wait ~ 0.7s
    elapsed = t1 - t0
    assert 0.6 <= elapsed <= 1.5
