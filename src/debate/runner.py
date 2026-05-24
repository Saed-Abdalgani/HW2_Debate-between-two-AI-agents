"""Debate session runner — live panel, exit codes (P8)."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from rich.live import Live

from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_stub_llm import JudgeDebateStubLLM
from debate.orchestration.state_machine import State
from debate.sdk.payloads import VerdictPayload
from debate.shared.child_env import debate_child_env
from debate.shared.config import Config
from debate.shared.diag_log import configure_diag_sink
from debate.shared.secrets import get_key
from debate.ui.status import render_panel, status_from_agent


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
    if not force_stub:
        get_key("LLM_API_KEY")
    use_stub = bool(force_stub)
    if use_stub:
        os.environ.setdefault("DEBATE_STUB_LLM", "echo")
    llm = JudgeDebateStubLLM() if use_stub else None
    child_env = debate_child_env(use_stub=use_stub)
    judge = JudgeAgent.build(cfg, llm=llm, child_env=child_env)
    _register_for_signals(judge)
    t0 = time.monotonic()
    judge._ui_started_at = t0
    judge._debate_llm_mode = "stub" if use_stub else "live"
    judge._ui_last_speaker = "—"

    def live_panel():
        return render_panel(status_from_agent(judge, speaker=judge._ui_last_speaker))

    if live:
        diag_path = judge.logger.run_dir / "judge.diag.log"
        configure_diag_sink(str(diag_path))
        try:
            with Live(get_renderable=live_panel, refresh_per_second=8) as panel:
                judge._live = panel
                panel.refresh()
                verdict = judge.run_debate(motion)
                judge._ui_last_speaker = "done"
                panel.refresh()
        finally:
            configure_diag_sink(None)
            sys.stderr.write(f"[RUNNER] Judge diagnostics log: {diag_path}\n")
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
