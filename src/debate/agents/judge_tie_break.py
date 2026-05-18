"""Deterministic tie-breaker when verdict validation fails twice (PLAN §6.4)."""

from __future__ import annotations

from debate.sdk.payloads import Role, ScorePayload, VerdictPayload, VerdictScores


def tie_break(history: list[ScorePayload], *, last_speaker: Role = Role.CON) -> VerdictPayload:
    """``argmax`` cumulative score; numeric tie → ``last_speaker`` (default ``con``)."""
    totals = {"pro": 0.0, "con": 0.0}
    for item in history:
        totals[item.for_role] += item.score
    if not history:
        winner: Role = last_speaker
        totals = {"pro": 0.0, "con": 0.0}
    elif totals["pro"] > totals["con"]:
        winner = Role.PRO
    elif totals["con"] > totals["pro"]:
        winner = Role.CON
    else:
        winner = last_speaker
    w = winner.value
    margin = abs(totals["pro"] - totals["con"])
    return VerdictPayload(
        winner=w,  # type: ignore[arg-type]
        reasons=[
            f"Tie-breaker: cumulative score pro={totals['pro']:.1f} con={totals['con']:.1f}.",
            (
                f"Numeric tie margin {margin:.1f}; last speaker "
                f"({last_speaker.value}) wins per PLAN 6.4."
            ),
            "Verdict LLM output failed validation twice; deterministic rule applied.",
        ],
        scores=VerdictScores(pro=totals["pro"], con=totals["con"]),
    )
