"""Behavioral test — judge cannot emit tied scores; tie-break is decisive."""

from __future__ import annotations

from pathlib import Path

import pytest

from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_stub_llm import JudgeDebateStubLLM
from debate.shared.config import load_config
from debate.shared.logger import Logger


@pytest.mark.integration
def test_5_dead_heat_judge_forces_winner_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PASS: Equal-score verdict JSON fails; tie-break yields unequal scores."""
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)

    bad_verdict = {
        "winner": "pro",
        "reasons": [
            "First analytical reason explaining why neither side was overwhelming.",
            "Second analytical reason comparing evidence quality in fine detail.",
            "Third analytical reason weighing rhetoric versus substance fairly.",
        ],
        "scores": {"pro": 50.0, "con": 50.0},
    }
    cfg = load_config().model_copy(
        update={"rounds": 1, "heartbeat_sec": 60.0, "heartbeat_timeout_sec": 30.0}
    )
    run = tmp_path / "runs" / "deadheat"
    logger = Logger(run, root=tmp_path)
    judge = JudgeAgent.build(
        cfg,
        llm=JudgeDebateStubLLM(custom_verdict=bad_verdict),
        logger=logger,
        stderr_dir=run / "stderr",
    )
    verdict = judge.run_debate("Both sides presented equally thin evidence on lunar mining")
    assert verdict.winner in ("pro", "con")
    assert verdict.scores.pro != verdict.scores.con
    assert (verdict.scores.pro > verdict.scores.con) or (verdict.scores.con > verdict.scores.pro)
    assert len(verdict.reasons) >= 3
