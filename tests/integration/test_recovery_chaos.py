"""Integration — chaos engineering with process kills (P9.2)."""

from __future__ import annotations

import os
import signal
from pathlib import Path

import pytest

from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_stub_llm import JudgeDebateStubLLM
from debate.orchestration.state_machine import State
from debate.shared.config import load_config
from debate.shared.logger import Logger


def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)


@pytest.mark.integration
def test_chaos_kill_pro_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    cfg = load_config().model_copy(
        update={
            "rounds": 2,
            "heartbeat_sec": 0.5,
            "heartbeat_timeout_sec": 0.5,
            "heartbeat_max_consecutive_misses": 2,
            "max_restarts_per_child": 2,
        }
    )
    run = tmp_path / "runs" / "full"
    logger = Logger(run, root=tmp_path)
    judge = JudgeAgent.build(
        cfg,
        llm=JudgeDebateStubLLM(),
        logger=logger,
        stderr_dir=run / "stderr",
    )

    killed = False
    original_on_turn = judge.on_turn

    def on_turn(speaker: str) -> None:
        nonlocal killed
        if original_on_turn:
            original_on_turn(speaker)
        # Kill pro when it's pro's turn and turn_id == 2 (first prompt reply was 1, next is 2)
        # Wait, the requirement says "wait for turn_id == 4" but rounds is 2.
        # turn_id increments on start, and then we have rounds.
        if judge._turn_id == 2 and speaker == "pro" and not killed:
            pro_child = judge.supervisor._children.get("pro")
            if pro_child:
                killed = True
                if hasattr(signal, "SIGKILL"):
                    os.kill(pro_child.process.pid, signal.SIGTERM)
                else:
                    pro_child.process.kill()
                # Sleep a tiny bit to ensure it dies before judge reads?
                # Actually, the supervisor reading from pipe will just get EOF or Timeout

    judge.on_turn = on_turn

    verdict = judge.run_debate("AI regulation should be stronger")
    assert killed, "Pro process was never killed"

    # Assert FSM resumed and completed
    assert judge._state == State.DONE
    assert verdict.winner in ("pro", "con")
    assert verdict.scores.pro != verdict.scores.con
    assert len(verdict.reasons) >= 3

    # Assert watchdog actually recorded a restart
    assert judge.watchdog is not None
    assert judge.watchdog.restarts("pro") > 0
