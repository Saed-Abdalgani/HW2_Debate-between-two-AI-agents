"""Unit tests — DebaterAgent compose, tool cap, prompt template (P6.5)."""

from __future__ import annotations

import queue
from datetime import UTC, datetime

import pytest

from debate.agents.debater_agent import load_debater_system, parse_tool_query
from debate.agents.pro_agent import ProAgent
from debate.agents.stub_llm import EchoStubLLM, ToolStormStubLLM
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
from debate.shared.gatekeeper import Gatekeeper


def _env(msg_type: MessageType, payload, *, turn_id: int = 1, role: Role = Role.JUDGE) -> Envelope:
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


def _wire_agent(agent: ProAgent, inbox: queue.Queue[Envelope], outbox: list[Envelope]) -> None:
    def fake_send(env: Envelope) -> None:
        outbox.append(env)
        if env.type == MessageType.TOOL_CALL:
            inbox.put(
                _env(
                    MessageType.TOOL_RESULT,
                    ToolResultPayload(
                        skill="search",
                        hits=[SearchHit(title="hit", url="https://x", snippet="fact")],
                        cached=False,
                    ),
                    turn_id=env.turn_id,
                )
            )

    agent.recv = lambda: inbox.get(timeout=3)  # type: ignore[method-assign]
    agent.send = fake_send  # type: ignore[method-assign]


@pytest.mark.unit
def test_parse_tool_query() -> None:
    assert parse_tool_query("TOOL:search:climate data 2024") == "climate data 2024"
    assert parse_tool_query("Plain argument.\nMore text.") is None


@pytest.mark.unit
def test_debater_system_template() -> None:
    text = load_debater_system("pro", "AI is good")
    assert "pro" in text
    assert "AI is good" in text


@pytest.mark.unit
def test_tool_call_cap(cfg) -> None:
    inbox: queue.Queue[Envelope] = queue.Queue()
    outbox: list[Envelope] = []
    agent = ProAgent(Role.PRO, cfg, Gatekeeper(cfg), ToolStormStubLLM(), None, None)  # type: ignore[arg-type]
    _wire_agent(agent, inbox, outbox)
    agent._on_init(
        InitPayload(motion="Test motion", stance="pro", rounds=3, max_tokens_per_turn=100)
    )
    reply = agent.compose_reply(
        PromptPayload(phase=DebatePhase.ARGUE, context=[], opponent_last="They said X."),
        turn_id=2,
    )
    tool_calls = [e for e in outbox if e.type == MessageType.TOOL_CALL]
    assert len(tool_calls) == 2
    assert reply.text.startswith("TOOL:search:query3")
    assert reply.tokens_in > 0


@pytest.mark.unit
def test_handle_three_prompts_via_run(cfg) -> None:
    inbox: queue.Queue[Envelope] = queue.Queue()
    outbox: list[Envelope] = []
    agent = ProAgent(Role.PRO, cfg, Gatekeeper(cfg), EchoStubLLM(), None, None)  # type: ignore[arg-type]
    _wire_agent(agent, inbox, outbox)
    inbox.put(
        _env(
            MessageType.INIT,
            InitPayload(motion="Remote work", stance="pro", rounds=3, max_tokens_per_turn=200),
        )
    )
    for turn_id, phase in enumerate(
        (DebatePhase.OPENING, DebatePhase.ARGUE, DebatePhase.CLOSING), start=1
    ):
        inbox.put(
            _env(
                MessageType.PROMPT,
                PromptPayload(phase=phase, context=[], opponent_last="opponent line"),
                turn_id=turn_id,
            )
        )
    inbox.put(_env(MessageType.SHUTDOWN, ShutdownPayload(reason="done")))
    assert agent.run() == 0
    replies = [e for e in outbox if e.type == MessageType.REPLY]
    assert len(replies) == 3
    for rep in replies:
        assert rep.payload.text  # type: ignore[union-attr]
