"""Behavioral test — Con uses search to challenge a false factual claim."""

from __future__ import annotations

import queue

import pytest
from behavioral_edge_wiring import wire_agent

from debate.agents.con_agent import ConAgent
from debate.agents.stub_llm import FactCheckStubLLM
from debate.sdk.payloads import DebatePhase, InitPayload, MessageType, PromptPayload, Role
from debate.shared.gatekeeper import Gatekeeper


@pytest.mark.unit
def test_2_blatant_lie_con_uses_search_tool_pass(cfg) -> None:
    """PASS: Con issues TOOL:search then rebuts using returned hits."""
    inbox: queue.Queue = queue.Queue()
    outbox: list = []
    agent = ConAgent(Role.CON, cfg, Gatekeeper(cfg), FactCheckStubLLM(), None, None)  # type: ignore[arg-type]
    wire_agent(agent, inbox, outbox)
    agent._on_init(
        InitPayload(
            motion="Geography knowledge matters for policy",
            stance="con",
            rounds=3,
            max_tokens_per_turn=200,
        )
    )
    lie = (
        "My opponent claims London is the capital of France — therefore their entire analogy holds."
    )
    reply = agent.compose_reply(
        PromptPayload(phase=DebatePhase.ARGUE, context=[], opponent_last=lie),
        turn_id=2,
    )
    tool_calls = [e for e in outbox if e.type == MessageType.TOOL_CALL]
    assert len(tool_calls) == 1
    query = tool_calls[0].payload.args.get("query", "")  # type: ignore[union-attr]
    assert query
    assert "paris" in reply.text.lower()
    assert "disprov" in reply.text.lower() or "false" in reply.text.lower()
