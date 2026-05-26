"""Per-turn scoring and summary updates for the Judge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from debate.agents.judge_rounds_support import (
    _log,
    compute_round_stats,
    detect_scoring_anomaly,
    validate_score_payload,
)
from debate.sdk.payloads import DebatePhase, ScorePayload

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent


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
    """Generate and store a round summary (standalone path)."""
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


def evaluate_round_batched(
    agent: JudgeAgent,
    pro_text: str,
    con_text: str,
    round_num: int,
    turn_id: int,
) -> None:
    """One judge LLM call: score Pro, score Con, write round summary (replaces 3 calls)."""
    from debate.agents.judge_prompts import load_score_rubric

    ctx_blocks = agent.gk.select_context("judge", turn_id)
    parts: list[str] = [
        load_score_rubric(),
        "",
        f"Motion: {agent._motion}",
        "",
        "=== CONTEXT (recent thread) ===",
    ]
    for block in ctx_blocks:
        parts.append(f"[{block.role}] {block.content[:600]}")
    parts.extend(
        [
            "",
            "=== PRO ARGUMENT (this round) ===",
            pro_text[:2000],
            "",
            "=== CON ARGUMENT (this round) ===",
            con_text[:2000],
            "",
            "Reply with ONLY the JSON object (no other text).",
        ]
    )
    user_blob = "\n".join(parts)
    try:
        raw = agent.router.invoke(
            "round_eval",
            {"text": user_blob, "round": round_num, "turn_id": turn_id},
        )
        pro_pl, con_pl, summary = raw  # type: ignore[misc]
    except Exception as exc:
        _log("round_eval_fallback", str(exc)[:120])
        score_reply(agent, "pro", pro_text, round_num, turn_id)
        score_reply(agent, "con", con_text, round_num, turn_id)
        summarise_round(agent, pro_text, con_text, turn_id)
        _log("round_eval", f"r{round_num} turn={turn_id} (fallback)")
        return
    for payload, text, role in (
        (pro_pl, pro_text, "pro"),
        (con_pl, con_text, "con"),
    ):
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
    if len(summary.strip()) < 10:
        _log("summary_short", f"turn={turn_id} len={len(summary)}")
    agent.gk.write_summary("judge", turn_id, summary)
    agent.gk.context.note_opponent("judge", con_text)
    agent.gk.context.note_reply("judge", pro_text)
    _log("round_eval", f"r{round_num} turn={turn_id}")


__all__ = [
    "compute_round_stats",
    "detect_scoring_anomaly",
    "evaluate_round_batched",
    "phase_for_round",
    "score_reply",
    "summarise_round",
    "validate_score_payload",
]
