"""Per-turn scoring and summary updates for the Judge.

Includes score validation, anomaly detection, round metadata logging,
and summary quality checks.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from debate.sdk.payloads import DebatePhase, ScorePayload
from debate.shared.diag_log import write_diag_line

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent

# Score validation bounds.
_MIN_SCORE = 0.0
_MAX_SCORE = 100.0
_ANOMALY_THRESHOLD = 0.01
_LOG_PREFIX = "[ROUNDS]"


def phase_for_round(round_num: int) -> DebatePhase:
    """Map a round number to a debate phase."""
    return DebatePhase.OPENING if round_num == 1 else DebatePhase.ARGUE


def score_reply(
    agent: JudgeAgent,
    role: str,
    text: str,
    round_num: int,
    turn_id: int,
) -> ScorePayload:
    """Score a debater's reply and validate the result."""
    ctx_blocks = agent.gk.select_context("judge", turn_id)
    parts = [f"Motion: {agent._motion}", f"Scoring {role} argument:"]
    for block in ctx_blocks:
        parts.append(f"[{block.role}] {block.content[:600]}")
    parts.append(text[:2000])
    payload = agent.router.invoke(
        "score",
        {
            "text": "\n".join(parts),
            "for_role": role,
            "round": round_num,
            "turn_id": turn_id,
        },
    )
    payload = validate_score_payload(payload)
    anomaly = detect_scoring_anomaly(agent._scores, payload)
    if anomaly:
        _log("score_anomaly", f"{role} r{round_num}: {anomaly}")
    agent._scores.append(payload)
    agent.logger.event(
        "score",
        role="judge",
        turn_id=turn_id,
        data=payload.model_dump(mode="json"),
    )
    _log(
        "scored",
        f"{role} r{round_num} score={payload.score:.1f} words={len(text.split())}",
    )
    return payload


def summarise_round(
    agent: JudgeAgent,
    pro_text: str,
    con_text: str,
    turn_id: int,
) -> None:
    """Generate and store a round summary for context compression."""
    blob = f"Pro: {pro_text[:400]}\nCon: {con_text[:400]}"
    summary = agent.router.invoke(
        "summarise",
        {"text": blob, "role": "judge", "turn_id": turn_id},
    )
    summary_str = str(summary)
    if len(summary_str.strip()) < 10:
        _log("summary_short", f"turn={turn_id} len={len(summary_str)}")
    agent.gk.write_summary("judge", turn_id, summary_str)
    agent.gk.context.note_opponent("judge", con_text)
    agent.gk.context.note_reply("judge", pro_text)


def validate_score_payload(payload: ScorePayload) -> ScorePayload:
    """Clamp score to [0, 100] and reject NaN/Inf."""
    score = payload.score
    if math.isnan(score) or math.isinf(score):
        _log("score_invalid", f"got {score}, clamping to 50.0")
        return payload.model_copy(update={"score": 50.0})
    clamped = max(_MIN_SCORE, min(_MAX_SCORE, score))
    if clamped != score:
        _log("score_clamped", f"{score:.1f} → {clamped:.1f}")
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
