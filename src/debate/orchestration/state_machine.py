"""Pure debate FSM (PLAN §5). No I/O, no LLM — trivially unit-testable."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    INIT = "INIT"
    SPAWNING = "SPAWNING"
    OPENING = "OPENING"
    PRO_TURN = "PRO_TURN"
    SCORE_PRO = "SCORE_PRO"
    CON_TURN = "CON_TURN"
    SCORE_CON = "SCORE_CON"
    NEXT_ROUND = "NEXT_ROUND"
    CLOSING = "CLOSING"
    VERDICT = "VERDICT"
    VALIDATE_VERDICT = "VALIDATE_VERDICT"
    TIE_BREAK = "TIE_BREAK"
    RECOVER = "RECOVER"
    DONE = "DONE"
    ABORT = "ABORT"


class Event(StrEnum):
    START = "start"
    CHILDREN_READY = "children_ready"
    SPAWN_FAILED = "spawn_failed"
    SENT_OPENINGS = "sent_openings"
    PRO_REPLY = "pro_reply"
    CON_REPLY = "con_reply"
    SCORED = "scored"
    CLOSINGS_RECEIVED = "closings_received"
    JUDGE_REPLY = "judge_reply"
    INVALID_OR_TIE = "invalid_or_tie"
    VALID_NON_TIE = "valid_non_tie"
    DETERMINISTIC_WINNER = "deterministic_winner"
    HEARTBEAT_MISS = "heartbeat_miss"
    RESPAWNED = "respawned"
    RESTARTS_EXHAUSTED = "restarts_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"


_TERMINAL = frozenset({State.DONE, State.ABORT})


@dataclass
class Ctx:
    """Mutable FSM context — round counters, retries, replay buffer."""

    round_limit: int
    round: int = 1
    verdict_retries: int = 0
    restarts_per_role: dict[str, int] = field(default_factory=dict)
    last_outbound_per_role: dict[str, str] = field(default_factory=dict)
    pending_recover_role: str | None = None
    pending_recover_return_to: State | None = None
    abort_reason: str | None = None


def is_terminal(state: State) -> bool:
    return state in _TERMINAL


_RECOVERABLE = {State.PRO_TURN: "pro", State.CON_TURN: "con"}


def transition(state: State, event: Event, ctx: Ctx, *, role: str | None = None) -> State:
    """Compute the next state. Mutates ``ctx`` for round / retry bookkeeping."""

    if event == Event.BUDGET_EXHAUSTED:
        ctx.abort_reason = "budget_exhausted"
        return State.ABORT

    if event == Event.HEARTBEAT_MISS:
        return _enter_recover(state, ctx, role)

    if event == Event.RESPAWNED and state == State.RECOVER:
        return _exit_recover(ctx)

    if event == Event.RESTARTS_EXHAUSTED and state == State.RECOVER:
        ctx.abort_reason = "child_unrecoverable"
        return State.ABORT

    if state == State.INIT and event == Event.START:
        return State.SPAWNING
    if state == State.SPAWNING and event == Event.CHILDREN_READY:
        return State.OPENING
    if state == State.SPAWNING and event == Event.SPAWN_FAILED:
        ctx.abort_reason = "spawn_failed"
        return State.ABORT
    if state == State.OPENING and event == Event.SENT_OPENINGS:
        return State.PRO_TURN
    if state == State.PRO_TURN and event == Event.PRO_REPLY:
        return State.SCORE_PRO
    if state == State.SCORE_PRO and event == Event.SCORED:
        return State.CON_TURN
    if state == State.CON_TURN and event == Event.CON_REPLY:
        return State.SCORE_CON
    if state == State.SCORE_CON and event == Event.SCORED:
        return _advance_round(ctx)
    if state == State.CLOSING and event == Event.CLOSINGS_RECEIVED:
        return State.VERDICT
    if state == State.VERDICT and event == Event.JUDGE_REPLY:
        return State.VALIDATE_VERDICT
    if state == State.VALIDATE_VERDICT and event == Event.VALID_NON_TIE:
        return State.DONE
    if state == State.VALIDATE_VERDICT and event == Event.INVALID_OR_TIE:
        return _verdict_retry(ctx)
    if state == State.TIE_BREAK and event == Event.DETERMINISTIC_WINNER:
        return State.DONE

    raise ValueError(f"illegal transition: {state} on {event}")


def _enter_recover(state: State, ctx: Ctx, role: str | None) -> State:
    return_to = _RECOVERABLE.get(state)
    if role is None or return_to != role:
        raise ValueError(f"heartbeat_miss not allowed from {state} for role={role!r}")
    ctx.pending_recover_role = role
    ctx.pending_recover_return_to = state
    return State.RECOVER


def _exit_recover(ctx: Ctx) -> State:
    target = ctx.pending_recover_return_to or State.PRO_TURN
    ctx.pending_recover_role = None
    ctx.pending_recover_return_to = None
    return target


def _advance_round(ctx: Ctx) -> State:
    if ctx.round >= ctx.round_limit:
        return State.CLOSING
    ctx.round += 1
    return State.PRO_TURN


def _verdict_retry(ctx: Ctx) -> State:
    if ctx.verdict_retries == 0:
        ctx.verdict_retries += 1
        return State.VERDICT
    return State.TIE_BREAK
