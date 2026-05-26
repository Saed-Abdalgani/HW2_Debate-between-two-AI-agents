"""Judge round scoring helpers: bounds, clamp, anomaly detection, diag."""

from __future__ import annotations

import math

from debate.sdk.payloads import ScorePayload
from debate.shared.diag_log import write_diag_line

_MIN_SCORE = 0.0
_MAX_SCORE = 100.0
_ANOMALY_THRESHOLD = 0.01
_LOG_PREFIX = "[ROUNDS]"


def validate_score_payload(payload: ScorePayload) -> ScorePayload:
    """Clamp score to [0, 100] and reject NaN/Inf."""
    score = payload.score
    if math.isnan(score) or math.isinf(score):
        _log("score_invalid", f"got {score}, clamping to 50.0")
        return payload.model_copy(update={"score": 50.0})
    clamped = max(_MIN_SCORE, min(_MAX_SCORE, score))
    if clamped != score:
        _log("score_clamped", f"{score:.1f} -> {clamped:.1f}")
        return payload.model_copy(update={"score": clamped})
    return payload


def detect_scoring_anomaly(
    history: list[ScorePayload],
    new: ScorePayload,
) -> str | None:
    """Detect suspicious scoring patterns."""
    if len(history) < 4:
        return None
    recent = [s.score for s in history[-4:]]
    if all(abs(s - recent[0]) < _ANOMALY_THRESHOLD for s in recent):
        return f"last 4 scores identical ({recent[0]:.1f})"
    spread = max(recent) - min(recent)
    if spread < _ANOMALY_THRESHOLD and abs(new.score - recent[0]) < _ANOMALY_THRESHOLD:
        return f"5 consecutive near-identical scores ({recent[0]:.1f})"
    return None


def compute_round_stats(
    scores: list[ScorePayload],
) -> dict[str, float]:
    """Compute aggregate statistics for debugging."""
    if not scores:
        return {"pro_avg": 0.0, "con_avg": 0.0, "total": 0}
    pro = [s.score for s in scores if s.for_role == "pro"]
    con = [s.score for s in scores if s.for_role == "con"]
    return {
        "pro_avg": sum(pro) / len(pro) if pro else 0.0,
        "con_avg": sum(con) / len(con) if con else 0.0,
        "total": len(scores),
    }


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    write_diag_line(msg)
