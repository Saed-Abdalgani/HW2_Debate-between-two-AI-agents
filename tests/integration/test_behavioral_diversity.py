"""Behavioral test — non-repetitive replies across many turns."""

from __future__ import annotations

import queue

import pytest
from behavioral_edge_wiring import wire_agent

from debate.agents.pro_agent import ProAgent
from debate.agents.stub_llm import EchoStubLLM
from debate.sdk.payloads import DebatePhase, InitPayload, PromptPayload, Role
from debate.shared.gatekeeper import Gatekeeper


@pytest.mark.unit
def test_4_ten_rounds_distinct_echo_pass(cfg) -> None:
    """PASS: Drifting opponent_last yields distinct echo replies."""
    agent = ProAgent(Role.PRO, cfg, Gatekeeper(cfg), EchoStubLLM(), None, None)  # type: ignore[arg-type]
    inbox: queue.Queue = queue.Queue()
    outbox: list = []
    wire_agent(agent, inbox, outbox)
    agent._on_init(
        InitPayload(motion="Energy policy", stance="pro", rounds=12, max_tokens_per_turn=300),
    )
    texts: list[str] = []
    for i in range(10):
        reply = agent.compose_reply(
            PromptPayload(
                phase=DebatePhase.ARGUE,
                context=[],
                opponent_last=f"Con angle {i}: markets, security, ethics, implementation risk.",
            ),
            turn_id=i + 1,
        )
        texts.append(reply.text)
    assert len(set(texts)) == 10
