"""Tie-break helpers: score stats, reason strings, display scores, history filter."""

from __future__ import annotations

import math

from debate.sdk.payloads import Role, ScorePayload, VerdictScores


def compute_score_stats(history: list[ScorePayload]) -> dict[str, object]:
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
    for r in ("pro", "con"):
        n = counts[r]
        avg = totals[r] / n if n > 0 else 0.0
        averages[r] = avg
        if n > 1:
            variance = (squares[r] / n) - (avg**2)
            stdevs[r] = math.sqrt(max(0.0, variance))
        else:
            stdevs[r] = 0.0

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
        f"Tie-breaker: cumulative score pro={totals['pro']:.1f} con={totals['con']:.1f}.",
    ]
    if margin < 1e-9:
        reasons.append(
            f"Cumulative totals were tied; role {last_speaker.value} is the configured "
            "numeric-tie decider per PLAN 6.4."
        )
    else:
        reasons.append(
            f"Cumulative margin {margin:.1f} points in favour of {winner.value} "
            "across scored rounds."
        )
    reasons.append("Verdict LLM output failed validation twice; deterministic rule applied.")
    if isinstance(avgs, dict) and avgs:
        pro_avg = avgs.get("pro", 0.0)
        con_avg = avgs.get("con", 0.0)
        reasons.append(f"Score averages: pro={pro_avg:.1f}, con={con_avg:.1f}.")
    if isinstance(momentum, dict) and momentum:
        pro_m = momentum.get("pro", 0.0)
        con_m = momentum.get("con", 0.0)
        reasons.append(f"Momentum (last - first): pro={pro_m:+.1f}, con={con_m:+.1f}.")
    return reasons[:5]


def verdict_scores_for_winner(
    totals: dict[str, float],
    winner: Role,
    *,
    counts: dict[str, int] | None = None,
    eps: float = 2.0,
) -> VerdictScores:
    """Map cumulative totals to 0-100 display scores with winner strictly ahead.

    Round scores are each on a 0-100 scale; cumulative sums can far exceed 100.
    Normalize by theoretical max (100 * scored rounds per side) before building
    ``VerdictScores`` (schema ``le=100``).
    """
    pt, ct = totals["pro"], totals["con"]
    if counts:
        n_pro = int(counts.get("pro", 0))
        n_con = int(counts.get("con", 0))
        denom = max(float(n_pro * 100), float(n_con * 100), 1.0)
    else:
        # Unknown round counts: scale by the larger cumulative so ratios stay ≤ 1.
        denom = max(pt, ct, 1.0)
    p_norm = min(100.0, max(0.0, (pt / denom) * 100.0))
    c_norm = min(100.0, max(0.0, (ct / denom) * 100.0))
    if winner == Role.PRO:
        if p_norm > c_norm:
            return VerdictScores(pro=p_norm, con=c_norm)
        bump = min(eps, max(0.1, 100.0 - p_norm, c_norm))
        return VerdictScores(
            pro=min(100.0, max(p_norm, c_norm) + bump),
            con=max(0.0, min(p_norm, c_norm) - bump),
        )
    if c_norm > p_norm:
        return VerdictScores(pro=p_norm, con=c_norm)
    bump = min(eps, max(0.1, 100.0 - c_norm, p_norm))
    return VerdictScores(
        pro=max(0.0, min(p_norm, c_norm) - bump),
        con=min(100.0, max(p_norm, c_norm) + bump),
    )


def validate_score_history(history: list[ScorePayload]) -> list[ScorePayload]:
    """Filter out corrupt entries (NaN/Inf scores)."""
    clean: list[ScorePayload] = []
    for item in history:
        if math.isnan(item.score) or math.isinf(item.score):
            continue
        if item.for_role not in ("pro", "con"):
            continue
        clean.append(item)
    return clean
