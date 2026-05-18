"""Debate session runner — live panel, exit codes (P8)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from rich.live import Live

from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_stub_llm import JudgeDebateStubLLM
from debate.orchestration.state_machine import State
from debate.sdk.payloads import VerdictPayload
from debate.shared.child_env import debate_child_env
from debate.shared.config import Config
from debate.shared.secrets import get_env
from debate.ui.status import DebateStatus, render_panel, status_from_agent


@dataclass(frozen=True)
class RunOutcome:
    verdict: VerdictPayload
    exit_code: int
    run_dir: str


def exit_code_for(agent: JudgeAgent) -> int:
    if agent._state == State.DONE:
        return 0
    if agent._state == State.ABORT:
        reason = agent._ctx.abort_reason or ""
        if reason == "budget_exhausted":
            return 2
        if reason == "child_unrecoverable":
            return 3
        return 1
    return 1


def run_debate(
    cfg: Config,
    motion: str,
    *,
    live: bool = True,
    force_stub: bool = False,
) -> RunOutcome:
    use_stub = force_stub or not get_env("LLM_API_KEY")
    if use_stub:
        os.environ.setdefault("DEBATE_STUB_LLM", "echo")
    llm = JudgeDebateStubLLM() if use_stub else None
    child_env = debate_child_env(use_stub=use_stub)
    judge = JudgeAgent.build(cfg, llm=llm, child_env=child_env)
    _register_for_signals(judge)
    status = DebateStatus(motion=motion, round_limit=cfg.rounds)

    def on_turn(speaker: str) -> None:
        nonlocal status
        status = status_from_agent(judge, speaker=speaker)

    judge.on_turn = on_turn

    if live:
        with Live(render_panel(status), refresh_per_second=4) as panel:
            judge._live = panel
            verdict = judge.run_debate(motion)
            panel.update(render_panel(status_from_agent(judge, speaker="done")))
    else:
        verdict = judge.run_debate(motion)

    return RunOutcome(
        verdict=verdict,
        exit_code=exit_code_for(judge),
        run_dir=str(judge.logger.run_dir),
    )


def _register_for_signals(judge: JudgeAgent) -> None:
    import debate.main as main_mod

    main_mod._AGENT = judge
