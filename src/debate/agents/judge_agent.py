"""Judge orchestrator — FSM driver, scoring, verdict pipeline (P7)."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from debate.agents.judge_agent_ops import (
    aborted_verdict,
    child_turn,
    closing_round,
    emit_abort,
    log_verdict,
    render_verdict,)
from debate.agents.judge_build import build_judge_agent
from debate.agents.judge_child import send_init
from debate.agents.judge_rounds import phase_for_round, score_reply, summarise_round
from debate.agents.judge_tie_break import tie_break
from debate.agents.judge_verdict import validate_verdict_stages
from debate.orchestration.state_machine import Ctx, Event, State, is_terminal, transition
from debate.orchestration.supervisor import Supervisor
from debate.orchestration.watchdog import Watchdog
from debate.sdk.payloads import ScorePayload, VerdictPayload
from debate.shared.budget import BudgetExceeded
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger
from debate.shared.router import SkillRouter
from debate.shared.skills import LLMClientProto

@dataclass
class JudgeAgent:
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
            cls, cfg, llm=llm, logger=logger, stderr_dir=stderr_dir, child_env=child_env
        )

    def _pulse(self, speaker: str) -> None:
        if self.on_turn:
            self.on_turn(speaker)
        if self._live is not None:
            from debate.ui.status import render_panel, status_from_agent

            self._live.update(render_panel(status_from_agent(self, speaker=speaker)))

    def run_debate(self, motion: str) -> VerdictPayload:
        self._motion = motion
        self._scores.clear()
        self._state = State.INIT
        self._ctx = Ctx(round_limit=self.cfg.rounds)
        if self.watchdog:
            self.watchdog.start()
        try:
            return self._drive(motion)
        except BudgetExceeded as exc:
            emit_abort(self, "budget_exhausted", detail=str(exc))
            self._state = State.ABORT
            return aborted_verdict(self)
        finally:
            if self.watchdog:
                self.watchdog.stop()
            self.supervisor.shutdown_all()
            self.logger.close()

    def _drive(self, motion: str) -> VerdictPayload:
        timeout = self.cfg.recv_default_timeout_sec
        self._state = transition(self._state, Event.START, self._ctx)
        try:
            self.supervisor.spawn("pro")
            self.supervisor.spawn("con")
        except Exception:
            self._state = transition(self._state, Event.SPAWN_FAILED, self._ctx)
            return aborted_verdict(self)
        self._turn_id += 1
        send_init(self.supervisor, self.cfg, motion, "pro", self._turn_id)
        send_init(self.supervisor, self.cfg, motion, "con", self._turn_id)
        self._state = transition(self._state, Event.CHILDREN_READY, self._ctx)
        self._state = transition(self._state, Event.SENT_OPENINGS, self._ctx)

        while not is_terminal(self._state):
            if self._state == State.PRO_TURN:
                self._last_pro = child_turn(self, "pro", phase_for_round(self._ctx.round), timeout)
                self._state = transition(self._state, Event.PRO_REPLY, self._ctx)
                score_reply(self, "pro", self._last_pro, self._ctx.round, self._turn_id)
                self._pulse("pro")
                self._state = transition(self._state, Event.SCORED, self._ctx)
            elif self._state == State.CON_TURN:
                self._last_con = child_turn(
                    self,
                    "con",
                    phase_for_round(self._ctx.round),
                    timeout,
                    opponent=self._last_pro,
                )
                self._state = transition(self._state, Event.CON_REPLY, self._ctx)
                score_reply(self, "con", self._last_con, self._ctx.round, self._turn_id)
                summarise_round(self, self._last_pro, self._last_con, self._turn_id)
                self._pulse("con")
                self._state = transition(self._state, Event.SCORED, self._ctx)
            elif self._state == State.CLOSING:
                closing_round(self, timeout)
                self._state = transition(self._state, Event.CLOSINGS_RECEIVED, self._ctx)
            elif self._state == State.VERDICT:
                raw = render_verdict(self)
                self._state = transition(self._state, Event.JUDGE_REPLY, self._ctx)
                check = validate_verdict_stages(raw)
                if check.ok and check.verdict:
                    self._state = transition(self._state, Event.VALID_NON_TIE, self._ctx)
                    log_verdict(self, check.verdict)
                    return check.verdict
                self._verdict_fail = f"{check.stage}: {check.reason}"
                self._state = transition(self._state, Event.INVALID_OR_TIE, self._ctx)
            elif self._state == State.TIE_BREAK:
                if not self._scores:
                    self.logger.event("tie_break_empty", role="judge", turn_id=self._turn_id)
                verdict = tie_break(self._scores)
                self._state = transition(self._state, Event.DETERMINISTIC_WINNER, self._ctx)
                log_verdict(self, verdict)
                return verdict
            elif self._state == State.ABORT:
                return aborted_verdict(self)
            else:
                raise RuntimeError(f"unexpected FSM state {self._state}")
        return aborted_verdict(self)