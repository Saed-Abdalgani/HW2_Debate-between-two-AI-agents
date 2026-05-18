"""Integration — end-to-end debate with stub LLM (P7.6, SC-1/SC-2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_stub_llm import JudgeDebateStubLLM
from debate.shared.config import load_config
from debate.shared.logger import Logger


def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)


@pytest.mark.integration
def test_full_debate_non_tie_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    cfg = load_config().model_copy(update={"rounds": 2, "heartbeat_sec": 60.0})
    run = tmp_path / "runs" / "full"
    logger = Logger(run, root=tmp_path)
    judge = JudgeAgent.build(
        cfg,
        llm=JudgeDebateStubLLM(),
        logger=logger,
        stderr_dir=run / "stderr",
    )
    verdict = judge.run_debate("AI regulation should be stronger")
    assert verdict.winner in ("pro", "con")
    assert verdict.scores.pro != verdict.scores.con
    assert len(verdict.reasons) >= 3
    assert all(len(r) >= 20 for r in verdict.reasons)

    log_path = run / "run.jsonl"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "verdict" in log_text
    assert not re.search(r"sk-testkey12345678901234567890", log_text)
