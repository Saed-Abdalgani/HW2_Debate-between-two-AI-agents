"""Judge orchestrator — FSM driver, scoring, verdict pipeline (P7)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from debate.agents.judge_agent_state import JudgeAgentStateMixin
from debate.agents.judge_build import build_judge_agent
from debate.agents.judge_motion import validate_motion
from debate.orchestration.state_machine import Ctx, State
from debate.orchestration.supervisor import Supervisor
from debate.orchestration.watchdog import Watchdog
from debate.sdk.payloads import ScorePayload, VerdictPayload
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger
from debate.shared.router import SkillRouter
from debate.shared.skills import LLMClientProto


@dataclass
class JudgeAgent(JudgeAgentStateMixin):
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
        validated = validate_motion(motion)
        self._log_lifecycle("debate_start", validated[:80])
        from debate.agents.judge_agent_runner import run_debate_impl

        return run_debate_impl(self, validated)

    def __repr__(self) -> str:
        return (
            f"<JudgeAgent state={self._state.value} round={self._ctx.round} turns={self._turn_id}>"
        )
