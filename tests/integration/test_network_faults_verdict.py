"""Integration — chaos engineering with network and provider faults (P9.4) - Verdict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from debate.agents.judge_agent import JudgeAgent
from debate.orchestration.state_machine import State
from debate.shared.config import load_config
from debate.shared.logger import Logger


@pytest.mark.integration
def test_simulated_bad_json_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulated bad JSON: stub LLM returns malformed verdict twice
    # -> assert tie-breaker engaged -> debate ends with deterministic winner.
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)

    cfg = load_config().model_copy(
        update={
            "rounds": 1,
        }
    )

    # We create a custom stub LLM for the judge
    from debate.agents.judge_stub_llm import JudgeDebateStubLLM
    from debate.sdk.llm_client import ChatResult

    class BadJsonStubLLM(JudgeDebateStubLLM):
        def __init__(self) -> None:
            super().__init__()
            self.verdict_calls = 0

        def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
            last = messages[-1]["content"]
            if "Return final verdict JSON" in last:
                self.verdict_calls += 1
                # Return bad JSON. It will fail semantic check (too few reasons or duplicate)
                return ChatResult(
                    text="""{
  "winner": "tie",
  "reasons": ["A", "B", "C"],
  "scores": {"pro": 100, "con": 100}
}""",
                    tokens_in=10,
                    tokens_out=10,
                    model="stub",
                )
            return super().chat(messages, max_tokens)

    run = tmp_path / "runs" / "full"
    logger = Logger(run, root=tmp_path)

    custom_llm = BadJsonStubLLM()

    judge = JudgeAgent.build(
        cfg,
        llm=custom_llm,
        logger=logger,
        stderr_dir=run / "stderr",
    )

    # Set up watchdog stub correctly so the test doesn't hang in RECOVER loop waiting for pong
    def _wd():
        from debate.orchestration.watchdog import Watchdog

        return Watchdog(
            judge.supervisor,
            heartbeat_sec=60.0,
            max_consecutive_misses=2,
            max_restarts_per_child=2,
            pong_check=lambda role: True,
            on_miss=lambda role: None,
        )

    judge.watchdog = _wd()

    # Set up watchdog stub correctly so the test doesn't hang in RECOVER loop waiting for pong
    def _wd2():
        from debate.orchestration.watchdog import Watchdog

        return Watchdog(
            judge.supervisor,
            heartbeat_sec=60.0,
            max_consecutive_misses=2,
            max_restarts_per_child=2,
            pong_check=lambda role: True,
            on_miss=lambda role: None,
        )

    judge.watchdog = _wd2()

    # We must ensure stub child actually replies to opening.
    # But wait, it uses custom JudgeDebateStubLLM but child uses the normal run path.
    # Actually, the stub LLM is used by judge and children.
    # What if we set DEBATE_STUB_LLM=echo like in test_debate_smoke.py?
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")

    verdict = judge.run_debate("AI regulation should be stronger")

    # Verdict validates failed twice. Let's check verdict logic in judge_agent
    # It tries VERDICT twice.
    assert custom_llm.verdict_calls == 2

    # Assert tie breaker engaged and debate ends with deterministic winner
    assert judge._state == State.DONE
    # Con wins on numerical tie or empty
    # Wait, the stub LLM for the child returns scores. The stub LLM parses the opening text?
    # In JudgeDebateStubLLM, score_reply parses and returns 85.0.
    # Both get 85.0! So con wins by tie breaker.
    assert verdict.winner == "con"
    assert any("Tie-breaker" in r for r in verdict.reasons)
