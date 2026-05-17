"""Integration: LLMClient through Gatekeeper updates the ledger."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from debate.sdk.llm_client import LLMClient
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger

_URL = "https://api.openai.com/v1/chat/completions"


@pytest.mark.integration
@respx.mock
def test_gatekeeper_llm_round_updates_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    cfg = load_config()
    run = tmp_path / "runs" / "wired"
    gk = Gatekeeper(
        cfg.model_copy(update={"retry_initial_delay_sec": 0.0, "retry_jitter_sec": 0.0}),
        logger=Logger(run, root=tmp_path),
        run_dir=run,
    )
    http = httpx.Client(timeout=httpx.Timeout(cfg.http_timeout_sec))
    llm = LLMClient(cfg.model, cfg.temperature, http)
    respx.post(_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "score=8.0\n- clear"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )
    )
    messages = [{"role": "user", "content": "Score this argument."}]
    estimate = gk.build_estimate(messages, cfg.model)
    result = gk.execute(
        lambda: llm.chat(messages, cfg.max_tokens_per_turn),
        estimate=estimate,
        role="judge",
        turn_id=1,
        model=cfg.model,
    )
    assert result.tokens_in == 100
    assert result.tokens_out == 50
    assert gk.ledger.tokens_in == 100
    assert gk.ledger.tokens_out == 50
    assert gk.ledger.usd_spent > Decimal("0")
    assert gk.ledger.requests >= 1
    log = (run / "run.jsonl").read_text(encoding="utf-8")
    assert "gatekeeper_call" in log
    assert "sk-test" not in log
