"""Judge runner — FSM execution loop with logging and error recovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from debate.agents.judge_agent_ops import aborted_verdict, emit_abort
from debate.agents.judge_child import send_init
from debate.agents.judge_runner_fsm import on_child_error, runner_log, step
from debate.orchestration.errors import ChildDisconnectedError, RecvTimeoutError
from debate.orchestration.state_machine import Ctx, Event, State, is_terminal, transition
from debate.sdk.payloads import VerdictPayload
from debate.shared.budget import BudgetExceeded

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent


def run_debate_impl(agent: JudgeAgent, motion: str) -> VerdictPayload:
    """Top-level debate execution with budget and lifecycle guards."""
    agent._motion = motion
    agent._scores.clear()
    agent._state = State.INIT
    agent._ctx = Ctx(round_limit=agent.cfg.rounds)
    runner_log("debate_begin", f"rounds={agent.cfg.rounds}")
    if agent.watchdog:
        agent.watchdog.start()
    try:
        return drive(agent, motion)
    except BudgetExceeded as exc:
        emit_abort(agent, "budget_exhausted", detail=str(exc))
        agent._state = State.ABORT
        return aborted_verdict(agent)
    finally:
        if agent.watchdog:
            agent.watchdog.stop()
        agent.supervisor.shutdown_all()
        agent.logger.close()
        runner_log("debate_end", f"state={agent._state.value}")


def drive(agent: JudgeAgent, motion: str) -> VerdictPayload:
    """Spawn children, run FSM loop, return verdict or abort."""
    timeout = agent.cfg.recv_default_timeout_sec
    agent._state = transition(agent._state, Event.START, agent._ctx)
    try:
        agent.supervisor.spawn("pro")
        agent.supervisor.spawn("con")
    except Exception:
        agent._state = transition(agent._state, Event.SPAWN_FAILED, agent._ctx)
        return aborted_verdict(agent)
    agent._turn_id += 1
    send_init(agent.supervisor, agent.cfg, motion, "pro", agent._turn_id)
    send_init(agent.supervisor, agent.cfg, motion, "con", agent._turn_id)
    agent._state = transition(agent._state, Event.CHILDREN_READY, agent._ctx)
    agent._state = transition(agent._state, Event.SENT_OPENINGS, agent._ctx)
    while not is_terminal(agent._state):
        try:
            result = step(agent, timeout)
            if result is not None:
                return result
        except (ChildDisconnectedError, RecvTimeoutError):
            on_child_error(agent)
    return aborted_verdict(agent)
