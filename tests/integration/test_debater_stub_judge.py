"""Integration — stub Judge drives Pro/Con via Supervisor (P6.5)."""

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
from debate.shared.config import load_config


def _envelope(msg_type: MessageType, payload, *, turn_id: int, role: Role = Role.JUDGE) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=role,
        type=msg_type,
        payload=payload,
    )


def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEBATE_STUB_LLM", "echo")
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)


def _drive(supervisor: Supervisor, stance: str, motion: str) -> list[Envelope]:
    role = stance
    supervisor.spawn(role)
    supervisor.send(
        role,
        _envelope(
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
            _envelope(
                MessageType.PROMPT,
                PromptPayload(phase=phase, context=[], opponent_last="Counterpoint."),
                turn_id=turn_id,
            ),
        )
        reply = _recv_reply(supervisor, role)
        assert reply.type == MessageType.REPLY
        replies.append(reply)
    supervisor.send(
        role, _envelope(MessageType.SHUTDOWN, ShutdownPayload(reason="done"), turn_id=99)
    )
    supervisor.terminate(role)
    return replies


def _recv_reply(supervisor: Supervisor, role: str) -> Envelope:
    while True:
        env = supervisor.recv(role, timeout=10.0)
        if env.type == MessageType.TOOL_CALL:
            supervisor.send(
                role,
                _envelope(
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


@pytest.fixture
def cfg():
    return load_config()


@pytest.mark.integration
def test_pro_three_replies(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        replies = _drive(sup, "pro", "AI helps humanity")
    finally:
        sup.shutdown_all()
    assert len(replies) == 3
    assert all(r.role == Role.PRO and r.payload.text for r in replies)  # type: ignore[union-attr]


@pytest.mark.integration
def test_con_three_replies(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        replies = _drive(sup, "con", "Remote work should stay default")
    finally:
        sup.shutdown_all()
    assert len(replies) == 3
    assert all(r.role == Role.CON for r in replies)


@pytest.mark.integration
def test_supervisor_strips_search_key(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    monkeypatch.setenv("SEARCH_API_KEY", "must-not-reach-child")
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        sup.spawn("pro")
        stderr_path = tmp_path / "stderr" / "pro.stderr.log"
        sup.terminate("pro")
    finally:
        sup.shutdown_all()
    assert not stderr_path.exists() or "must-not-reach-child" not in stderr_path.read_text(
        encoding="utf-8", errors="ignore"
    )
    child = sup._safe_child_env()
    assert "SEARCH_API_KEY" not in child


@pytest.mark.integration
def test_child_env_has_no_search_key(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch)
    monkeypatch.setenv("SEARCH_API_KEY", "stripped")
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    env = sup._safe_child_env()
    assert "SEARCH_API_KEY" not in env
    assert "LLM_API_KEY" in env
