"""Judge ↔ child IPC helpers (init, prompt, tool proxy, reply)."""

from __future__ import annotations

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


def judge_envelope(msg_type: MessageType, payload, *, turn_id: int) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=msg_type,
        payload=payload,
    )


def send_init(supervisor: Supervisor, cfg: Config, motion: str, stance: str, turn_id: int) -> None:
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
            PromptPayload(phase=phase, context=context, opponent_last=opponent_last),
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
        if env.type == MessageType.TOOL_CALL:
            result = router.dispatch(env.payload)  # type: ignore[arg-type]
            supervisor.send(
                role,
                judge_envelope(MessageType.TOOL_RESULT, result, turn_id=env.turn_id),
            )
            continue
        return env


def shutdown_child(supervisor: Supervisor, role: str, turn_id: int) -> None:
    supervisor.send(
        role,
        judge_envelope(MessageType.SHUTDOWN, ShutdownPayload(reason="debate_end"), turn_id=turn_id),
    )
    supervisor.terminate(role)
