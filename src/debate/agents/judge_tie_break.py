"""Deterministic tie-breaker when verdict validation fails twice.

Includes score history validation, statistical analysis (per-round
averages, standard deviation, momentum), detailed tie-break reasoning,
and edge case handling (PLAN §6.4).
"""

from __future__ import annotations

import math

from debate.sdk.payloads import Role, ScorePayload, VerdictPayload, VerdictScores


def tie_break(
    history: list[ScorePayload],
    *,
    last_speaker: Role = Role.CON,
) -> VerdictPayload:
    """``argmax`` cumulative score; numeric tie → ``last_speaker``."""
    clean = _validate_history(history)
    stats = compute_score_stats(clean)
    totals = stats["totals"]

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
    reasons = format_tie_break_analysis(winner, totals, margin, last_speaker, stats)
    return VerdictPayload(
        winner=winner.value,  # type: ignore[arg-type]
        reasons=reasons,
        scores=VerdictScores(pro=totals["pro"], con=totals["con"]),
    )


def compute_score_stats(
    history: list[ScorePayload],
) -> dict[str, object]:
    """Compute per-role aggregates: totals, averages, stdev, momentum."""
    totals: dict[str, float] = {"pro": 0.0, "con": 0.0}
    counts: dict[str, int] = {"pro": 0, "con": 0}
    squares: dict[str, float] = {"pro": 0.0, "con": 0.0}
    last_scores: dict[str, float] = {"pro": 0.0, "con": 0.0}
    first_scores: dict[str, float] = {"pro": 0.0, "con": 0.0}

    for item in history:
        role = item.for_role
        totals[role] += item.score
        counts[role] += 1
        squares[role] += item.score**2
        last_scores[role] = item.score
        if counts[role] == 1:
            first_scores[role] = item.score

    averages: dict[str, float] = {}
    stdevs: dict[str, float] = {}
    for role in ("pro", "con"):
        n = counts[role]
        avg = totals[role] / n if n > 0 else 0.0
        averages[role] = avg
        if n > 1:
            variance = (squares[role] / n) - (avg**2)
            stdevs[role] = math.sqrt(max(0.0, variance))
        else:
            stdevs[role] = 0.0

    momentum: dict[str, float] = {
        "pro": last_scores["pro"] - first_scores["pro"],
        "con": last_scores["con"] - first_scores["con"],
    }

    return {
        "totals": totals,
        "averages": averages,
        "stdevs": stdevs,
        "momentum": momentum,
        "counts": counts,
    }


def format_tie_break_analysis(
    winner: Role,
    totals: dict[str, float],
    margin: float,
    last_speaker: Role,
    stats: dict[str, object],
) -> list[str]:
    """Build detailed, human-readable tie-break reasons."""
    avgs = stats.get("averages", {})
    momentum = stats.get("momentum", {})
    reasons = [
        (f"Tie-breaker: cumulative score pro={totals['pro']:.1f} con={totals['con']:.1f}."),
        (
            f"Numeric tie margin {margin:.1f}; last speaker "
            f"({last_speaker.value}) wins per PLAN 6.4."
        ),
        ("Verdict LLM output failed validation twice; deterministic rule applied."),
    ]
    if isinstance(avgs, dict) and avgs:
        pro_avg = avgs.get("pro", 0.0)
        con_avg = avgs.get("con", 0.0)
        reasons.append(f"Score averages: pro={pro_avg:.1f}, con={con_avg:.1f}.")
    if isinstance(momentum, dict) and momentum:
        pro_m = momentum.get("pro", 0.0)
        con_m = momentum.get("con", 0.0)
        reasons.append(f"Momentum (last - first): pro={pro_m:+.1f}, con={con_m:+.1f}.")
    return reasons[:5]


def _validate_history(
    history: list[ScorePayload],
) -> list[ScorePayload]:
    """Filter out corrupt entries (NaN/Inf scores)."""
    clean: list[ScorePayload] = []
    for item in history:
        if math.isnan(item.score) or math.isinf(item.score):
            continue
        if item.for_role not in ("pro", "con"):
            continue
        clean.append(item)
    return clean
