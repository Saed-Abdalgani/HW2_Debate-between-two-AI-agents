"""Integration — Supervisor + echo child round-trip 10 envelopes (P5.6)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from debate.orchestration.supervisor import Supervisor
from debate.sdk.payloads import (
    MessageType,
    PingPayload,
    ReplyPayload,
    Role,
    ShutdownPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import load_config

_ECHO = Path(__file__).resolve().parent / "echo_child.py"


def _envelope(msg_type: MessageType, payload, turn_id: int, role: Role = Role.JUDGE) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=role,
        type=msg_type,
        payload=payload,
    )


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def supervisor(cfg, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCH_API_KEY", "should-be-stripped")
    monkeypatch.setenv("LLM_API_KEY", "should-survive")
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    yield sup
    sup.shutdown_all()


@pytest.mark.integration
def test_round_trip_ten_envelopes(supervisor: Supervisor) -> None:
    supervisor.spawn("pro", argv=[sys.executable, str(_ECHO)])
    for i in range(1, 11):
        payload = ReplyPayload(text=f"m{i}", tokens_in=1, tokens_out=1)
        env = _envelope(MessageType.REPLY, payload, i, role=Role.PRO)
        supervisor.send("pro", env)
        echoed = supervisor.recv("pro", timeout=5.0)
        assert echoed.type == MessageType.REPLY
        assert echoed.turn_id == i
    supervisor.send(
        "pro",
        _envelope(MessageType.SHUTDOWN, ShutdownPayload(reason="done"), 99, role=Role.JUDGE),
    )
    supervisor.terminate("pro")


@pytest.mark.integration
def test_ping_pong_protocol(supervisor: Supervisor) -> None:
    supervisor.spawn("pro", argv=[sys.executable, str(_ECHO)])
    supervisor.send("pro", _envelope(MessageType.PING, PingPayload(), 42))
    reply = supervisor.recv("pro", timeout=5.0)
    assert reply.type == MessageType.PONG
    assert reply.turn_id == 42
    supervisor.terminate("pro")


@pytest.mark.integration
def test_search_api_key_stripped_from_child_env(supervisor: Supervisor, tmp_path: Path) -> None:
    supervisor.spawn("pro", argv=[sys.executable, str(_ECHO)])
    supervisor.send(
        "pro",
        _envelope(MessageType.SHUTDOWN, ShutdownPayload(reason="done"), 1, role=Role.JUDGE),
    )
    supervisor.terminate("pro")
    stderr_file = tmp_path / "stderr" / "pro.stderr.log"
    contents = stderr_file.read_text(encoding="utf-8", errors="ignore")
    assert "__env__=LLM_API_KEY" in contents
    assert "SEARCH_API_KEY" not in contents
