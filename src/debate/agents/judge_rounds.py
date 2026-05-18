"""Per-turn scoring and summary updates for the Judge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from debate.sdk.payloads import DebatePhase, ScorePayload

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent


def phase_for_round(round_num: int) -> DebatePhase:
    return DebatePhase.OPENING if round_num == 1 else DebatePhase.ARGUE


def score_reply(
    agent: JudgeAgent, role: str, text: str, round_num: int, turn_id: int
) -> ScorePayload:
0    ctx_blocks = agent.gk.select_context("judge", turn_id)
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
    agent._scores.append(payload)
    agent.logger.event(
        "score",
        role="judge",
        turn_id=turn_id,
        data=payload.model_dump(mode="json"),
    )
    return payload


def summarise_round(agent: JudgeAgent, pro_text: str, con_text: str, turn_id: int) -> None:
    blob = f"Pro: {pro_text[:400]}\nCon: {con_text[:400]}"
    summary = agent.router.invoke(
        "summarise",
        {"text": blob, "role": "judge", "turn_id": turn_id},
    )
    agent.gk.write_summary("judge", turn_id, str(summary))
    agent.gk.context.note_opponent("judge", con_text)
    agent.gk.context.note_reply("judge", pro_text)
