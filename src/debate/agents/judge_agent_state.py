"""JudgeAgent inspection helpers and lifecycle logging."""

from __future__ import annotations

import sys


class JudgeAgentStateMixin:
    """State inspection and logging mixed into ``JudgeAgent``."""

    def is_running(self) -> bool:
        from debate.orchestration.state_machine import is_terminal

        return not is_terminal(self._state)

    def current_round(self) -> int:
        return self._ctx.round

    def scores_summary(self) -> dict[str, float]:
        totals: dict[str, float] = {"pro": 0.0, "con": 0.0}
        for s in self._scores:
            totals[s.for_role] += s.score
        return totals

    def score_trend(self) -> dict[str, list[float]]:
        trend: dict[str, list[float]] = {"pro": [], "con": []}
        for s in self._scores:
            trend[s.for_role].append(s.score)
        return trend

    def debate_stats(self) -> dict[str, object]:
        return {
            "state": self._state.value,
            "round": self._ctx.round,
            "turn_id": self._turn_id,
            "scores_count": len(self._scores),
            "scores_summary": self.scores_summary(),
            "motion_len": len(self._motion),
        }

    def preflight_check(self) -> list[str]:
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
