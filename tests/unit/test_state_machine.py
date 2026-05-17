"""Unit tests — FSM edges from PLAN §5 (P5.2)."""

from __future__ import annotations

import pytest

from debate.orchestration.state_machine import Ctx, Event, State, is_terminal, transition


def _ctx(round_limit: int = 2) -> Ctx:
    return Ctx(round_limit=round_limit)


@pytest.mark.unit
def test_happy_path_one_round_to_done() -> None:
    ctx = _ctx(round_limit=1)
    state = State.INIT
    for event in (
        Event.START,
        Event.CHILDREN_READY,
        Event.SENT_OPENINGS,
        Event.PRO_REPLY,
        Event.SCORED,
        Event.CON_REPLY,
        Event.SCORED,
        Event.CLOSINGS_RECEIVED,
        Event.JUDGE_REPLY,
        Event.VALID_NON_TIE,
    ):
        state = transition(state, event, ctx)
    assert state == State.DONE
    assert is_terminal(state)


@pytest.mark.unit
def test_next_round_advances_until_limit() -> None:
    ctx = _ctx(round_limit=2)
    state = State.SCORE_CON
    state = transition(state, Event.SCORED, ctx)
    assert state == State.PRO_TURN
    assert ctx.round == 2
    state = State.SCORE_CON
    state = transition(state, Event.SCORED, ctx)
    assert state == State.CLOSING


@pytest.mark.unit
def test_verdict_retry_then_tie_break() -> None:
    ctx = _ctx()
    state = transition(State.VALIDATE_VERDICT, Event.INVALID_OR_TIE, ctx)
    assert state == State.VERDICT
    assert ctx.verdict_retries == 1
    state = transition(State.VALIDATE_VERDICT, Event.INVALID_OR_TIE, ctx)
    assert state == State.TIE_BREAK
    state = transition(state, Event.DETERMINISTIC_WINNER, ctx)
    assert state == State.DONE


@pytest.mark.unit
@pytest.mark.parametrize("from_state", list(State))
def test_budget_exhausted_aborts_from_any(from_state: State) -> None:
    ctx = _ctx()
    state = transition(from_state, Event.BUDGET_EXHAUSTED, ctx)
    assert state == State.ABORT
    assert is_terminal(state)
    assert ctx.abort_reason == "budget_exhausted"


@pytest.mark.unit
def test_spawn_failed_aborts() -> None:
    ctx = _ctx()
    state = transition(State.SPAWNING, Event.SPAWN_FAILED, ctx)
    assert state == State.ABORT
    assert ctx.abort_reason == "spawn_failed"


@pytest.mark.unit
def test_recover_resumes_originating_role() -> None:
    ctx = _ctx()
    state = transition(State.PRO_TURN, Event.HEARTBEAT_MISS, ctx, role="pro")
    assert state == State.RECOVER
    assert ctx.pending_recover_role == "pro"
    state = transition(state, Event.RESPAWNED, ctx)
    assert state == State.PRO_TURN
    assert ctx.pending_recover_role is None


@pytest.mark.unit
def test_recover_from_con_turn() -> None:
    ctx = _ctx()
    state = transition(State.CON_TURN, Event.HEARTBEAT_MISS, ctx, role="con")
    assert state == State.RECOVER
    state = transition(state, Event.RESPAWNED, ctx)
    assert state == State.CON_TURN


@pytest.mark.unit
def test_restarts_exhausted_aborts() -> None:
    ctx = _ctx()
    state = transition(State.PRO_TURN, Event.HEARTBEAT_MISS, ctx, role="pro")
    state = transition(state, Event.RESTARTS_EXHAUSTED, ctx)
    assert state == State.ABORT
    assert ctx.abort_reason == "child_unrecoverable"


@pytest.mark.unit
def test_heartbeat_miss_rejects_wrong_role() -> None:
    ctx = _ctx()
    with pytest.raises(ValueError):
        transition(State.PRO_TURN, Event.HEARTBEAT_MISS, ctx, role="con")


@pytest.mark.unit
def test_illegal_transition_raises() -> None:
    ctx = _ctx()
    with pytest.raises(ValueError):
        transition(State.INIT, Event.PRO_REPLY, ctx)


@pytest.mark.unit
def test_is_terminal() -> None:
    assert is_terminal(State.DONE)
    assert is_terminal(State.ABORT)
    assert not is_terminal(State.PRO_TURN)
