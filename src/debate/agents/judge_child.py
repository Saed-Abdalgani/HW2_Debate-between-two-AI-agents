"""Judge ↔ child IPC helpers (init, prompt, tool proxy, reply).
Includes envelope validation, tool dispatch safety, graceful handling
of unexpected message types, and structured recv logging.
"""
from __future__ import annotations
import sys
from datetime import UTC, datetime
from debate.orchestration.supervisor import Supervisor
from debate.sdk.payloads import (
    ContextMessage,
    DebatePhase,
    InitPayload,
    MessageType,
    PromptPayload,
    Role,
    ShutdownPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import Config
from debate.shared.router import SkillRouter

_LOG_PREFIX = "[CHILD]"

def judge_envelope(msg_type: MessageType, payload: object, *, turn_id: int) -> Envelope:
    """Build a Judge-stamped envelope with current UTC timestamp."""
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=msg_type,
        payload=payload,
    )


def send_init(
    supervisor: Supervisor,
    cfg: Config,
    motion: str,
    stance: str,
    turn_id: int,
) -> None:
    """Send INIT to a child debater, validating payload first."""
    if not motion.strip():
        raise ValueError("cannot send INIT with empty motion")
    if stance not in ("pro", "con"):
        raise ValueError(f"invalid stance for INIT: {stance!r}")
    supervisor.send(
        stance,
        judge_envelope(
            MessageType.INIT,
            InitPayload(
                motion=motion,
                stance=stance,  # type: ignore[arg-type]
                rounds=cfg.rounds,
                max_tokens_per_turn=cfg.max_tokens_per_turn,
            ),
            turn_id=turn_id,
        ),
    )
    _log("init_sent", f"stance={stance} turn={turn_id}")

def send_prompt(
    supervisor: Supervisor,
    role: str,
    *,
    phase: DebatePhase,
    context: list[ContextMessage],
    opponent_last: str | None,
    turn_id: int,
) -> None:
    """Send a PROMPT envelope to a child debater."""
    supervisor.send(
        role,
        judge_envelope(
            MessageType.PROMPT,
            PromptPayload(
                phase=phase,
                context=context,
                opponent_last=opponent_last,
            ),
            turn_id=turn_id,
        ),
    )
def recv_reply(
    supervisor: Supervisor,
    role: str,
    router: SkillRouter,
    *,
    timeout: float,
) -> Envelope:
    """Receive from a child, handling tool calls and events inline."""
    while True:
        env = supervisor.recv(role, timeout=timeout)
        if env.type == MessageType.TOOL_CALL:
            _handle_tool_call(supervisor, role, router, env)
            continue
        if env.type == MessageType.PONG:
            continue
        if env.type == MessageType.EVENT:
            _handle_event(env)
        return env

def _handle_tool_call(
    supervisor: Supervisor,
    role: str,
    router: SkillRouter,
    env: Envelope,
) -> None:
    """Validate and dispatch a tool call, returning results."""
    payload = env.payload
    if not hasattr(payload, "skill") or not payload.skill:
        _log("invalid_tool_call", f"{role}: missing skill field")
        return
    result = router.dispatch(payload)  # type: ignore[arg-type]
    supervisor.send(
        role,
        judge_envelope(MessageType.TOOL_RESULT, result, turn_id=env.turn_id),
    )

def _handle_event(env: Envelope) -> None:
    """Process EVENT envelopes — raise on budget exhaustion."""
    from debate.shared.budget import BudgetExceeded

    if not hasattr(env.payload, "name"):
        return
    if env.payload.name != "agent_error":
        return
    data = getattr(env.payload, "data", {})
    if data.get("error") == "BudgetExceeded":
        raise BudgetExceeded(data.get("detail", "child budget exhausted"), {})

def shutdown_child(supervisor: Supervisor, role: str, turn_id: int) -> None:
    """Send SHUTDOWN and terminate a child process."""
    supervisor.send(
        role,
        judge_envelope(
            MessageType.SHUTDOWN,
            ShutdownPayload(reason="debate_end"),
            turn_id=turn_id,
        ),
    )
    supervisor.terminate(role)
    _log("shutdown", f"role={role}")

def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")