"""Judge FSM step handlers: per-state transitions and verdict pipeline."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from debate.agents.judge_agent_ops import (
    aborted_verdict,
    child_turn,
    closing_round,
    log_verdict,
    render_verdict,
)
from debate.agents.judge_rounds import phase_for_round, score_reply, summarise_round
from debate.agents.judge_tie_break import tie_break
from debate.agents.judge_verdict import validate_verdict_stages
from debate.orchestration.state_machine import Event, State, transition
from debate.sdk.payloads import VerdictPayload
from debate.shared.diag_log import write_diag_line

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent

_LOG = "[RUNNER]"


def step(agent: JudgeAgent, timeout: float) -> VerdictPayload | None:
    s = agent._state
    if s == State.PRO_TURN:
        agent._last_pro = child_turn(agent, "pro", phase_for_round(agent._ctx.round), timeout)
        agent._state = transition(s, Event.PRO_REPLY, agent._ctx)
        score_reply(agent, "pro", agent._last_pro, agent._ctx.round, agent._turn_id)
        agent._state = transition(agent._state, Event.SCORED, agent._ctx)
        agent._pulse("pro")
    elif s == State.CON_TURN:
        agent._last_con = child_turn(
            agent,
            "con",
            phase_for_round(agent._ctx.round),
            timeout,
            opponent=agent._last_pro,
        )
        agent._state = transition(s, Event.CON_REPLY, agent._ctx)
        score_reply(agent, "con", agent._last_con, agent._ctx.round, agent._turn_id)
        summarise_round(agent, agent._last_pro, agent._last_con, agent._turn_id)
        agent._state = transition(agent._state, Event.SCORED, agent._ctx)
        agent._pulse("con")
    elif s == State.CLOSING:
        closing_round(agent, timeout)
        agent._state = transition(s, Event.CLOSINGS_RECEIVED, agent._ctx)
    elif s == State.VERDICT:
        return try_verdict(agent)
    elif s == State.TIE_BREAK:
        return do_tie_break(agent)
    elif s == State.ABORT:
        return aborted_verdict(agent)
    elif s == State.RECOVER:
        time.sleep(0.5)
        agent._state = transition(s, Event.RESPAWNED, agent._ctx)
    else:
        raise RuntimeError(f"unexpected FSM state {s}")
    return None


def try_verdict(agent: JudgeAgent) -> VerdictPayload | None:
    raw = render_verdict(agent)
    agent._state = transition(agent._state, Event.JUDGE_REPLY, agent._ctx)
    check = validate_verdict_stages(raw)
    if check.ok and check.verdict:
        agent._state = transition(agent._state, Event.VALID_NON_TIE, agent._ctx)
        log_verdict(agent, check.verdict)
        return check.verdict
    agent._verdict_fail = f"{check.stage}: {check.reason}"
    agent._state = transition(agent._state, Event.INVALID_OR_TIE, agent._ctx)
    return None


def do_tie_break(agent: JudgeAgent) -> VerdictPayload:
    if not agent._scores:
        agent.logger.event("tie_break_empty", role="judge", turn_id=agent._turn_id)
    verdict = tie_break(agent._scores)
    agent._state = transition(agent._state, Event.DETERMINISTIC_WINNER, agent._ctx)
    log_verdict(agent, verdict)
    return verdict


def on_child_error(agent: JudgeAgent) -> None:
    if agent._ctx.abort_reason == "child_unrecoverable":
        agent._state = State.ABORT
        return
    role = "pro" if agent._state == State.PRO_TURN else "con"
    if agent._state in (State.PRO_TURN, State.CON_TURN):
        agent._state = transition(agent._state, Event.HEARTBEAT_MISS, agent._ctx, role=role)


def runner_log(event: str, detail: str = "") -> None:
    write_diag_line(f"{_LOG} {event}: {detail}" if detail else f"{_LOG} {event}")
