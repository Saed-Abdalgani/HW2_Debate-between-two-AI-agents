"""Tests for built-in Router skill factories (search / summarise / score)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from debate.sdk.llm_client import ChatResult
from debate.sdk.payloads import SearchHit, ToolCallPayload
from debate.shared.config import load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.router import SkillRouter
from debate.shared.skills import make_score_skill, make_search_skill, make_summarise_skill


@dataclass
class _StubSearch:
    calls: int = 0

    def query(self, text: str, k: int) -> list[SearchHit]:
        self.calls += 1
        return [SearchHit(title=text[:5], url="https://x", snippet=f"top-{k}")]


@dataclass
class _StubLLM:
    response: str
    tokens_in: int = 5
    tokens_out: int = 5

    def chat(self, messages: list[dict[str, Any]], max_tokens: int) -> ChatResult:
        return ChatResult(
            text=self.response,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            model="gpt-4o-mini",
        )


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def gk(cfg):
    return Gatekeeper(cfg)


@pytest.mark.unit
def test_search_skill_goes_through_gatekeeper(cfg, gk: Gatekeeper) -> None:
    stub = _StubSearch()
    router = SkillRouter(cfg)
    router.register("search", make_search_skill(stub, gk))
    out = router.dispatch(ToolCallPayload(skill="search", args={"query": "x", "k": 3}))
    assert out.cached is False
    assert stub.calls == 1
    assert gk.ledger.requests == 1


@pytest.mark.unit
def test_summarise_skill_caps_output(gk: Gatekeeper) -> None:
    llm = _StubLLM(response="round one in brief")
    skill = make_summarise_skill(llm, gk, system_prompt="summarise concisely", model="gpt-4o-mini")
    out = skill({"text": "a very long debate transcript", "turn_id": 2})
    assert out == "round one in brief"
    assert gk.ledger.requests == 1
    assert gk.ledger.tokens_in == llm.tokens_in


@pytest.mark.unit
def test_score_skill_parses_rubric_response(gk: Gatekeeper) -> None:
    response = "score=7.5\n- clear framing\n- weak rebuttal"
    skill = make_score_skill(_StubLLM(response), gk, rubric="rate 0..10", model="gpt-4o-mini")
    payload = skill({"text": "argued well", "for_role": "pro", "round": 2})
    assert payload.score == 7.5
    assert payload.points == ["clear framing", "weak rebuttal"]
    assert payload.for_role == "pro"
    assert payload.round == 2


@pytest.mark.unit
def test_score_skill_tolerates_bad_score(gk: Gatekeeper) -> None:
    response = "score=banana\n- only one"
    skill = make_score_skill(_StubLLM(response), gk, rubric="rate", model="gpt-4o-mini")
    payload = skill({"text": "x", "for_role": "con", "round": 1})
    assert payload.score == 0.0
    assert payload.points == ["only one"]
