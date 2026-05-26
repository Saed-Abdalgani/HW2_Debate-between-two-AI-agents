"""Unit tests — Select/Write keeps scoring prompts bounded (P7.4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from debate.agents.judge_rounds import score_reply
from debate.shared.config import load_config
from debate.shared.context_store import ContextStore
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.router import SkillRouter
from debate.shared.skills import make_score_skill


class _CapturingLLM:
    def __init__(self) -> None:
        self.last_messages: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, Any]], max_tokens: int, *, response_format=None):
        from debate.sdk.llm_client import ChatResult

        self.last_messages = messages
        return ChatResult(
            text="score=7.0\n- clear\n- focused",
            tokens_in=3,
            tokens_out=5,
            model="gpt-4o-mini",
        )


def _mock_agent(cfg, gk, router) -> MagicMock:
    agent = MagicMock()
    agent.cfg = cfg
    agent.gk = gk
    agent.router = router
    agent._motion = "Test motion"
    agent._scores = []
    agent.logger = MagicMock()
    return agent


@pytest.mark.unit
def test_select_context_at_most_three_blocks() -> None:
    store = ContextStore()
    store.set_summary("judge", "rolling summary of prior rounds only")
    store.note_reply("judge", "pro spoke last")
    store.note_opponent("judge", "con spoke last")
    blocks = store.select_context("judge", turn_id=9)
    assert len(blocks) <= 3


@pytest.mark.unit
def test_score_reply_truncates_context_in_prompt() -> None:
    cfg = load_config()
    gk = Gatekeeper(cfg, context=ContextStore())
    llm = _CapturingLLM()
    router = SkillRouter(cfg)
    router.register("score", make_score_skill(llm, gk, rubric="rate debate", model=cfg.score_model))
    agent = _mock_agent(cfg, gk, router)
    gk.context.set_summary("judge", "brief summary only")
    gk.context.note_opponent("judge", "MARKER " + ("word " * 4000))
    score_reply(agent, "pro", "current turn argument", 1, 1)
    user_blob = llm.last_messages[-1]["content"]
    assert "current turn argument" in user_blob
    assert len(user_blob) < 2500
