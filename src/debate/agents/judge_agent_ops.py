"""JudgeAgent turn helpers — child prompts, verdict LLM, logging.
Includes reply validation, verdict audit logging, detailed abort reasons,
and structured event emission for scoring and child turns.
"""
from __future__ import annotations
import sys
from typing import TYPE_CHECKING
from debate.agents.judge_child import recv_reply, send_prompt, shutdown_child
from debate.agents.judge_prompts import load_judge_system
from debate.sdk.payloads import (
    DebatePhase,
    MessageType,
    VerdictPayload,
    VerdictScores,)
if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent

# Reply validation limits.
_MAX_REPLY_LENGTH = 15_000
_MIN_REPLY_LENGTH = 2
_LOG_PREFIX = "[OPS]"


def child_turn(
    agent: JudgeAgent,
    role: str,
    phase: DebatePhase,
    timeout: float,
    *,
    opponent: str | None = None,
) -> str:
    """Send prompt, receive reply, validate, and update context."""
    agent._turn_id += 1
    ctx = agent.gk.select_context(role, agent._turn_id)
    send_prompt(
        agent.supervisor,
        role,
        phase=phase,
        context=ctx,
        opponent_last=opponent,
        turn_id=agent._turn_id,
    )
    agent._ctx.last_outbound_per_role[role] = phase.value
    env = recv_reply(agent.supervisor, role, agent.router, timeout=timeout)
    if env.type != MessageType.REPLY:
        raise ValueError(f"expected reply from {role}, got {env.type}")
    text = env.payload.text  # type: ignore[union-attr]
    _validate_child_reply(text, role, agent._turn_id)
    agent.gk.context.note_reply(role, text)
    if opponent is not None:
        agent.gk.context.note_opponent(role, opponent)
    _log(f"{role}_reply", f"turn={agent._turn_id} len={len(text)}")
    return text


def closing_round(agent: JudgeAgent, timeout: float) -> None:
    """Collect closing statements from both sides and shutdown children."""
    for role, opp in (("pro", agent._last_con), ("con", agent._last_pro)):
        agent._turn_id += 1
        send_prompt(
            agent.supervisor,
            role,
            phase=DebatePhase.CLOSING,
            context=agent.gk.select_context(role, agent._turn_id),
            opponent_last=opp,
            turn_id=agent._turn_id,
        )
        recv_reply(agent.supervisor, role, agent.router, timeout=timeout)
    shutdown_child(agent.supervisor, "pro", agent._turn_id)
    shutdown_child(agent.supervisor, "con", agent._turn_id)
    _log("closings_done", f"turn={agent._turn_id}")

def render_verdict(agent: JudgeAgent) -> str:
    """Ask the LLM for a verdict JSON based on accumulated scores."""
    system = load_judge_system(agent._motion, retry_note=agent._verdict_fail)
    history = "\n".join(f"{s.for_role} r{s.round}: {s.score}" for s in agent._scores[-20:])
    _log("verdict_request", f"scores={len(agent._scores)}")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (f"Debate scores:\n{history}\nReturn final verdict JSON."),
        },
    ]
    estimate = agent.gk.build_estimate(messages, agent.cfg.judge_model)
    result = agent.gk.execute(
        lambda: agent.llm.chat(messages, agent.cfg.max_tokens_for_verdict),
        estimate=estimate,
        role="judge",
        turn_id=agent._turn_id,
        model=agent.cfg.judge_model,
    )
    return result.text

def log_verdict(agent: JudgeAgent, verdict: VerdictPayload) -> None:
    """Persist the verdict to the structured event log."""
    agent.logger.event(
        "verdict",
        role="judge",
        turn_id=agent._turn_id,
        data=verdict.model_dump(mode="json"),
    )
    _log("verdict_logged", f"winner={verdict.winner}")

def aborted_verdict(agent: JudgeAgent) -> VerdictPayload:
    """Produce a deterministic verdict when the debate is aborted."""
    reason = agent._ctx.abort_reason or "aborted"
    agent.logger.event(
        "verdict",
        role="judge",
        turn_id=agent._turn_id,
        data={
            "outcome": reason,
            "round": agent._ctx.round,
            "turn": agent._turn_id,
        },
    )
    return VerdictPayload(
        winner="con",
        reasons=[
            f"Debate aborted: {reason} — default outcome applied.",
            "Transcript preserved for review per recovery semantics.",
            "No validated LLM verdict was produced before abort.",
        ],
        scores=VerdictScores(pro=0.0, con=0.0),
    )
def emit_abort(agent: JudgeAgent, name: str, *, detail: str = "") -> None:
    """Record an abort event and set the abort reason on the FSM context."""
    agent.logger.event(
        name,
        role="judge",
        turn_id=agent._turn_id,
        data={"detail": detail},
    )
    agent._ctx.abort_reason = name

def _validate_child_reply(text: str, role: str, turn_id: int) -> None:
    """Warn on suspiciously short or long child replies."""
    if len(text) < _MIN_REPLY_LENGTH:
        _log("reply_too_short", f"{role} turn={turn_id} len={len(text)}")
    if len(text) > _MAX_REPLY_LENGTH:
        _log("reply_too_long", f"{role} turn={turn_id} len={len(text)}")

def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")