"""Unit tests — multi-stage verdict validation (P7.2)."""

from __future__ import annotations

import json

import pytest

from debate.agents.judge_verdict import validate_verdict_stages
from debate.orchestration.state_machine import Ctx, Event, State, transition

_GOOD = {
    "winner": "pro",
    "reasons": [
        "Pro consistently linked claims to cited evidence across rounds.",
        "Con dropped the central trade-off after the second rebuttal.",
        "Pro's closing integrated search results without overreach.",
    ],
    "scores": {"pro": 78.0, "con": 61.0},
}


@pytest.mark.unit
def test_schema_fail_on_invalid_json() -> None:
    check = validate_verdict_stages("not json at all")
    assert not check.ok
    assert check.stage == "schema"


@pytest.mark.unit
def test_semantic_fail_duplicate_reasons() -> None:
    bad = dict(_GOOD)
    dup = "Pro consistently linked claims to cited evidence across rounds."
    bad["reasons"] = [dup, dup, "Third distinct reason with enough length."]
    check = validate_verdict_stages(json.dumps(bad))
    assert not check.ok
    assert check.stage == "semantic"


@pytest.mark.unit
def test_consistency_fail_winner_contradicts_scores() -> None:
    bad = dict(_GOOD)
    bad["winner"] = "con"
    check = validate_verdict_stages(json.dumps(bad))
    assert not check.ok
    assert check.stage == "consistency"


@pytest.mark.unit
def test_success_on_valid_payload() -> None:
    check = validate_verdict_stages(json.dumps(_GOOD))
    assert check.ok
    assert check.verdict is not None
    assert check.verdict.winner == "pro"


@pytest.mark.unit
def test_fsm_retry_then_tie_break_path() -> None:
    ctx = Ctx(round_limit=2)
    state = transition(State.VALIDATE_VERDICT, Event.INVALID_OR_TIE, ctx)
    assert state == State.VERDICT
    assert ctx.verdict_retries == 1
    state = transition(State.VALIDATE_VERDICT, Event.INVALID_OR_TIE, ctx)
    assert state == State.TIE_BREAK
    state = transition(state, Event.DETERMINISTIC_WINNER, ctx)
    assert state == State.DONE
