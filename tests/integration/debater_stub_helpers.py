"""Shared helpers — stub Judge driving Pro/Con via Supervisor (P6.5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from debate.orchestration.supervisor import Supervisor
from debate.sdk.payloads import (
    DebatePhase,
    InitPayload,
    MessageType,
    PromptPayload,
    Role,
    SearchHit,
    ShutdownPayload,
    ToolResultPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope


def envelope(msg_type: MessageType, payload, *, turn_id: int, role: Role = Role.JUDGE) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=role,
        type=msg_type,
        payload=payload,
    )


def stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)


def drive_three_phases(supervisor: Supervisor, stance: str, motion: str) -> list[Envelope]:
    role = stance
    supervisor.spawn(role)
    supervisor.send(
        role,
        envelope(
            MessageType.INIT,
            InitPayload(
                motion=motion,
                stance=stance,  # type: ignore[arg-type]
                rounds=3,
                max_tokens_per_turn=200,
            ),
            turn_id=0,
        ),
    )
    replies: list[Envelope] = []
    for turn_id, phase in enumerate(
        (DebatePhase.OPENING, DebatePhase.ARGUE, DebatePhase.CLOSING), start=1
    ):
        supervisor.send(
            role,
            envelope(
                MessageType.PROMPT,
                PromptPayload(phase=phase, context=[], opponent_last="Counterpoint."),
                turn_id=turn_id,
            ),
        )
        reply = recv_reply_handling_tools(supervisor, role)
        assert reply.type == MessageType.REPLY
        replies.append(reply)
    supervisor.send(
        role, envelope(MessageType.SHUTDOWN, ShutdownPayload(reason="done"), turn_id=99)
    )
    supervisor.terminate(role)
    return replies


def recv_reply_handling_tools(supervisor: Supervisor, role: str) -> Envelope:
    while True:
        env = supervisor.recv(role, timeout=10.0)
        if env.type == MessageType.TOOL_CALL:
            supervisor.send(
                role,
                envelope(
                    MessageType.TOOL_RESULT,
                    ToolResultPayload(
                        skill="search",
                        hits=[SearchHit(title="t", url="https://example.com", snippet="evidence")],
                        cached=False,
                    ),
                    turn_id=env.turn_id,
                ),
            )
            continue
        return env
