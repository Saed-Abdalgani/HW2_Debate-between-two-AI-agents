"""Behavioral test — IPC JSON survives markdown, quotes, newlines."""

from __future__ import annotations

import json
import queue

import pytest
from behavioral_edge_wiring import envelope, wire_agent

from debate.agents.pro_agent import ProAgent
from debate.sdk.llm_client import ChatResult
from debate.sdk.payloads import (
    DebatePhase,
    InitPayload,
    MessageType,
    PromptPayload,
    ReplyPayload,
    Role,
)
from debate.sdk.schemas import serialize
from debate.shared.gatekeeper import Gatekeeper


class _NoiseStubLLM:
    model = "gpt-4o-mini"

    def chat(self, messages: list, max_tokens: int) -> ChatResult:
        return ChatResult(
            text=(
                "**Bold** claim: He said \"nested 'quotes'\" then `code` — "
                'Hebrew: שלום — backslash\\\\path — "\\""'
            ),
            tokens_in=2,
            tokens_out=40,
            model="gpt-4o-mini",
        )


class _NlStubLLM:
    model = "gpt-4o-mini"

    def chat(self, messages: list, max_tokens: int) -> ChatResult:
        return ChatResult(
            text='First line.\nSecond "line" with\nnewlines.',
            tokens_in=2,
            tokens_out=20,
            model="gpt-4o-mini",
        )


@pytest.mark.unit
def test_3_json_resilience_ipc_serialize_pass(cfg) -> None:
    """PASS: Complex reply text serializes as one valid JSON line."""
    inbox: queue.Queue = queue.Queue()
    outbox: list = []
    agent = ProAgent(Role.PRO, cfg, Gatekeeper(cfg), _NoiseStubLLM(), None, None)  # type: ignore[arg-type]
    wire_agent(agent, inbox, outbox)
    agent._on_init(InitPayload(motion="Test", stance="pro", rounds=2, max_tokens_per_turn=200))
    r1 = agent.compose_reply(
        PromptPayload(phase=DebatePhase.OPENING, context=[], opponent_last=None),
        turn_id=1,
    )
    line = serialize(
        envelope(
            MessageType.REPLY,
            ReplyPayload(text=r1.text, tokens_in=1, tokens_out=2),
            turn_id=1,
            role=Role.PRO,
        )
    )
    assert "\n" not in json.loads(line.strip())["payload"]["text"]

    inbox2: queue.Queue = queue.Queue()
    agent2 = ProAgent(Role.PRO, cfg, Gatekeeper(cfg), _NlStubLLM(), None, None)  # type: ignore[arg-type]
    wire_agent(agent2, inbox2, [])
    agent2._on_init(InitPayload(motion="Test", stance="pro", rounds=2, max_tokens_per_turn=200))
    r2 = agent2.compose_reply(
        PromptPayload(phase=DebatePhase.ARGUE, context=[], opponent_last="x"),
        turn_id=2,
    )
    assert "\n" not in r2.text
    json.loads(
        serialize(
            envelope(
                MessageType.REPLY,
                ReplyPayload(text=r2.text, tokens_in=1, tokens_out=2),
                turn_id=2,
                role=Role.PRO,
            )
        ).strip()
    )
