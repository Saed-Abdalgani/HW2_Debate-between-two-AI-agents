"""Deterministic tie-breaker when verdict validation fails twice."""

from __future__ import annotations

from debate.agents.judge_tie_break_support import (
    compute_score_stats,
    format_tie_break_analysis,
    validate_score_history,
    verdict_scores_for_winner,
)
from debate.sdk.payloads import Role, ScorePayload, VerdictPayload


def tie_break(
    history: list[ScorePayload],
    *,
    last_speaker: Role = Role.CON,
) -> VerdictPayload:
    """``argmax`` cumulative score; numeric tie → ``last_speaker``."""
    clean = validate_score_history(history)
    stats = compute_score_stats(clean)
    totals: dict[str, float] = stats["totals"]  # type: ignore[assignment]
    counts: dict[str, int] = stats["counts"]  # type: ignore[assignment]

    if not clean:
        winner: Role = last_speaker
        totals = {"pro": 0.0, "con": 0.0}
    elif totals["pro"] > totals["con"]:
        winner = Role.PRO
    elif totals["con"] > totals["pro"]:
        winner = Role.CON
    else:
        winner = last_speaker

    margin = abs(totals["pro"] - totals["con"])
    scores = verdict_scores_for_winner(totals, winner, counts=counts)
    reasons = format_tie_break_analysis(winner, totals, margin, last_speaker, stats)
    return VerdictPayload(
        winner=winner.value,  # type: ignore[arg-type]
        reasons=reasons,
        scores=scores,
    )
