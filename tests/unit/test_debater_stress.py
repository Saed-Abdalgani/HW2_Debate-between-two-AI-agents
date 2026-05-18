"""Stress — rapid ping/pong without dropped envelopes (P6.5 optional)."""

from __future__ import annotations

import queue
from datetime import UTC, datetime

import pytest

from debate.agents.base_agent import BaseAgent
from debate.sdk.payloads import MessageType, PingPayload, Role, ShutdownPayload
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper


class _PingOnlyAgent(BaseAgent):
    def handle(self, env: Envelope) -> None:
        raise AssertionError("should not receive non-ping messages")


def _env(msg_type: MessageType, payload, turn_id: int) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=msg_type,
        payload=payload,
    )


@pytest.mark.unit
def test_fifty_ping_pong_storm() -> None:
    cfg = load_config()
    inbox: queue.Queue[Envelope] = queue.Queue()
    outbox: list[Envelope] = []
    agent = _PingOnlyAgent(Role.CON, cfg, Gatekeeper(cfg), object(), None, None)  # type: ignore[arg-type]
    agent.recv = lambda: inbox.get(timeout=3)  # type: ignore[method-assign]
    agent.send = lambda env: outbox.append(env)  # type: ignore[method-assign]
    for i in range(1, 51):
        inbox.put(_env(MessageType.PING, PingPayload(), turn_id=i))
    inbox.put(_env(MessageType.SHUTDOWN, ShutdownPayload(reason="done"), turn_id=99))
    assert agent.run() == 0
    assert len(outbox) == 50
    assert all(e.type == MessageType.PONG for e in outbox)
