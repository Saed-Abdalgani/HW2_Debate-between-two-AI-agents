"""Judge orchestrator — FSM driver, scoring, verdict pipeline (P7).
Includes motion validation, state inspection, pre-flight checks,
structured lifecycle logging, and safety sanitisation.
"""
from __future__ import annotations
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from debate.agents.judge_build import build_judge_agent
from debate.orchestration.state_machine import Ctx, State
from debate.orchestration.supervisor import Supervisor
from debate.orchestration.watchdog import Watchdog
from debate.sdk.payloads import ScorePayload, VerdictPayload
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger
from debate.shared.router import SkillRouter
from debate.shared.skills import LLMClientProto

# Validation limits for the motion string.
_MAX_MOTION_LENGTH = 2000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class JudgeAgent:
    """Orchestrates a full Pro-vs-Con debate and produces a verdict."""

    cfg: Config
    gk: Gatekeeper
    llm: LLMClientProto
    supervisor: Supervisor
    router: SkillRouter
    logger: Logger
    watchdog: Watchdog | None = None
    on_turn: Callable[[str], None] | None = None
    _live: Any = None
    _motion: str = ""
    _turn_id: int = 0
    _scores: list[ScorePayload] = field(default_factory=list)
    _last_pro: str = ""
    _last_con: str = ""
    _verdict_fail: str = ""
    _state: State = State.INIT
    _ctx: Ctx = field(default_factory=lambda: Ctx(round_limit=1))

    @classmethod
    def build(
        cls,
        cfg: Config,
        *,
        llm: LLMClientProto | None = None,
        logger: Logger | None = None,
        stderr_dir: Any = None,
        child_env: dict[str, str] | None = None,
    ) -> JudgeAgent:
        return build_judge_agent(
            cls,
            cfg,
            llm=llm,
            logger=logger,
            stderr_dir=stderr_dir,
            child_env=child_env,
        )

    def _pulse(self, speaker: str) -> None:
        if self.on_turn:
            self.on_turn(speaker)
        if self._live is not None:
            from debate.ui.status import render_panel, status_from_agent

            self._live.update(render_panel(status_from_agent(self, speaker=speaker)))

    def run_debate(self, motion: str) -> VerdictPayload:
        """Validate motion, then delegate to the FSM runner."""
        validated = _validate_motion(motion)
        self._log_lifecycle("debate_start", validated[:80])
        from debate.agents.judge_agent_runner import run_debate_impl

        return run_debate_impl(self, validated)

    # --- Inspection helpers ----------------------------------------
    def is_running(self) -> bool:
        """Return ``True`` if the FSM is in a non-terminal state."""
        from debate.orchestration.state_machine import is_terminal

        return not is_terminal(self._state)

    def current_round(self) -> int:
        """Return the current debate round number."""
        return self._ctx.round

    def scores_summary(self) -> dict[str, float]:
        """Aggregate scores per role across all rounds."""
        totals: dict[str, float] = {"pro": 0.0, "con": 0.0}
        for s in self._scores:
            totals[s.for_role] += s.score
        return totals

    def score_trend(self) -> dict[str, list[float]]:
        """Return per-role score lists in order for trend analysis."""
        trend: dict[str, list[float]] = {"pro": [], "con": []}
        for s in self._scores:
            trend[s.for_role].append(s.score)
        return trend

    def debate_stats(self) -> dict[str, object]:
        """Return a summary of the current debate state."""
        return {
            "state": self._state.value,
            "round": self._ctx.round,
            "turn_id": self._turn_id,
            "scores_count": len(self._scores),
            "scores_summary": self.scores_summary(),
            "motion_len": len(self._motion),
        }

    def preflight_check(self) -> list[str]:
        """Verify components are wired before starting a debate."""
        issues: list[str] = []
        if self.llm is None:
            issues.append("LLM client is not set")
        if self.supervisor is None:
            issues.append("Supervisor is not set")
        if self.router is None:
            issues.append("SkillRouter is not set")
        if self.logger is None:
            issues.append("Logger is not set")
        return issues

    def _log_lifecycle(self, event: str, detail: str = "") -> None:
        msg = f"[JUDGE] {event}"
        if detail:
            msg += f": {detail}"
        sys.stderr.write(msg + "\n")

    def __repr__(self) -> str:
        return (
            f"<JudgeAgent state={self._state.value} round={self._ctx.round} turns={self._turn_id}>"
        )
def _validate_motion(motion: str) -> str:
    """Sanitise and validate the motion string."""
    cleaned = _CONTROL_CHARS.sub("", motion).strip()
    if not cleaned:
        raise ValueError("motion must not be empty")
    if len(cleaned) > _MAX_MOTION_LENGTH:
        raise ValueError(f"motion exceeds {_MAX_MOTION_LENGTH} chars (got {len(cleaned)})")
    return cleaned