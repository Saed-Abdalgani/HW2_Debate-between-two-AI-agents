"""Judge ↔ child turn helpers: prompts, reply recv, closing round."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from debate.agents.judge_child import recv_reply, send_prompt, shutdown_child
from debate.sdk.payloads import DebatePhase, MessageType
from debate.shared.diag_log import write_diag_line

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent

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
    while True:
        env = recv_reply(agent.supervisor, role, agent.router, timeout=timeout)
        sys.stderr.write(f"[DEBUG] IPC got: {env.type}\n")
        if env.type == MessageType.REPLY:
            break
        if env.type == MessageType.EVENT:
            _log(f"{role}_ipc_event", f"turn={agent._turn_id}")
            continue
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


def _validate_child_reply(text: str, role: str, turn_id: int) -> None:
    if len(text) < _MIN_REPLY_LENGTH:
        _log("reply_too_short", f"{role} turn={turn_id} len={len(text)}")
    if len(text) > _MAX_REPLY_LENGTH:
        _log("reply_too_long", f"{role} turn={turn_id} len={len(text)}")


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    write_diag_line(msg)
