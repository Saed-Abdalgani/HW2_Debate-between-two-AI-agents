"""Unit tests — deterministic tie-breaker (P7.3)."""

from __future__ import annotations

import pytest

from debate.agents.judge_tie_break import tie_break
from debate.sdk.payloads import Role, ScorePayload

_LONG = "x" * 20


@pytest.mark.unit
def test_asymmetric_scores_pro_wins() -> None:
    history = [
        ScorePayload(for_role="pro", round=1, points=[_LONG], score=8.0),
        ScorePayload(for_role="con", round=1, points=[_LONG], score=3.0),
    ]
    verdict = tie_break(history)
    assert verdict.winner == "pro"
    assert verdict.scores.pro > verdict.scores.con


@pytest.mark.unit
def test_exact_cumulative_tie_con_wins() -> None:
    history = [
        ScorePayload(for_role="pro", round=1, points=[_LONG], score=5.0),
        ScorePayload(for_role="con", round=1, points=[_LONG], score=5.0),
    ]
    verdict = tie_break(history, last_speaker=Role.CON)
    assert verdict.winner == "con"
    assert verdict.scores.con > verdict.scores.pro


@pytest.mark.unit
def test_empty_history_defaults_to_con() -> None:
    verdict = tie_break([])
    assert verdict.winner == "con"
    assert verdict.scores.con > verdict.scores.pro
    assert len(verdict.reasons) >= 3


@pytest.mark.unit
def test_high_cumulative_totals_normalized_to_verdict_schema() -> None:
    """Cumulative 0-100-per-round scores can sum > 100; VerdictScores must stay <= 100."""
    history = [
        ScorePayload(for_role="pro", round=r, points=[_LONG], score=82.0) for r in range(1, 11)
    ] + [ScorePayload(for_role="con", round=r, points=[_LONG], score=74.0) for r in range(1, 11)]
    verdict = tie_break(history)
    assert verdict.winner == "pro"
    assert verdict.scores.pro <= 100.0
    assert verdict.scores.con <= 100.0
    assert verdict.scores.pro > verdict.scores.con
