"""Unit tests — BaseAgent ping/pong, shutdown, agent_error (P6.5)."""

from __future__ import annotations

import queue
from datetime import UTC, datetime

import pytest

from debate.agents.base_agent import AGENT_ERROR_EXIT, CLEAN_EXIT, BaseAgent
from debate.sdk.payloads import (
    DebatePhase,
    MessageType,
    PingPayload,
    PromptPayload,
    Role,
    ShutdownPayload,
)
from debate.sdk.schemas import SCHEMA_VERSION, Envelope
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper


class _StubLLM:
    def chat(self, messages, max_tokens):
        from debate.sdk.llm_client import ChatResult

        return ChatResult(text="ok", tokens_in=1, tokens_out=1, model="gpt-4o-mini")


class _HarnessAgent(BaseAgent):
    def handle(self, env: Envelope) -> None:
        if env.type == MessageType.PROMPT:
            raise RuntimeError("intentional failure")


def _env(msg_type: MessageType, payload, *, turn_id: int = 1) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=msg_type,
        payload=payload,
    )


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def wired(cfg):
    inbox: queue.Queue[Envelope] = queue.Queue()
    outbox: list[Envelope] = []
    gk = Gatekeeper(cfg)
    llm = _StubLLM()
    reader = writer = None  # type: ignore[assignment]
    agent = _HarnessAgent(Role.PRO, cfg, gk, llm, reader, writer)
    agent.recv = lambda: inbox.get(timeout=2)  # type: ignore[method-assign]
    agent.send = lambda env: outbox.append(env)  # type: ignore[method-assign]
    return agent, inbox, outbox


@pytest.mark.unit
def test_ping_pong(wired) -> None:
    agent, inbox, outbox = wired
    inbox.put(_env(MessageType.PING, PingPayload(), turn_id=5))
    inbox.put(_env(MessageType.SHUTDOWN, ShutdownPayload(reason="done")))
    assert agent.run() == CLEAN_EXIT
    assert len(outbox) == 1
    assert outbox[0].type == MessageType.PONG
    assert outbox[0].payload.turn_id == 5  # type: ignore[union-attr]


@pytest.mark.unit
def test_shutdown_exits_cleanly(wired) -> None:
    agent, inbox, outbox = wired
    inbox.put(_env(MessageType.SHUTDOWN, ShutdownPayload(reason="bye")))
    assert agent.run() == CLEAN_EXIT
    assert outbox == []


@pytest.mark.unit
def test_uncaught_exception_emits_agent_error(wired) -> None:
    agent, inbox, outbox = wired
    inbox.put(
        _env(
            MessageType.PROMPT,
            PromptPayload(phase=DebatePhase.OPENING, context=[], opponent_last=None),
        )
    )
    assert agent.run() == AGENT_ERROR_EXIT
    assert outbox[-1].type == MessageType.EVENT
    assert outbox[-1].payload.name == "agent_error"  # type: ignore[union-attr]
