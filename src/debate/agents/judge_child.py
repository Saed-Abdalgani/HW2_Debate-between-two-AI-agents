"""Judge ↔ child IPC helpers (init, prompt, tool proxy, reply)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from debate.agents.judge_child_envelope import judge_envelope
from debate.agents.judge_child_handlers import handle_event, handle_tool_call
from debate.sdk.payloads import (
    ContextMessage,
    DebatePhase,
    InitPayload,
    MessageType,
    PromptPayload,
    ShutdownPayload,
)
from debate.sdk.schemas import Envelope
from debate.shared.config import Config

if TYPE_CHECKING:
    from debate.orchestration.supervisor import Supervisor
    from debate.shared.router import SkillRouter

_LOG_PREFIX = "[CHILD]"


def send_init(
    supervisor: Supervisor,
    cfg: Config,
    motion: str,
    stance: str,
    turn_id: int,
) -> None:
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
    while True:
        env = supervisor.recv(role, timeout=timeout)
        sys.stderr.write(f"[DEBUG] IPC recv {role}: type={env.type} turn_id={env.turn_id}\n")
        if env.type == MessageType.TOOL_CALL:
            handle_tool_call(supervisor, role, router, env)
            continue
        if env.type == MessageType.PONG:
            continue
        if env.type == MessageType.EVENT:
            handle_event(env)
            continue
        return env


def shutdown_child(supervisor: Supervisor, role: str, turn_id: int) -> None:
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
