"""Judge verdict LLM call, logging, abort paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

from debate.agents.judge_prompts import load_judge_system
from debate.sdk.payloads import VerdictPayload, VerdictScores
from debate.shared.diag_log import write_diag_line

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent

_LOG_PREFIX = "[OPS]"


def render_verdict(agent: JudgeAgent) -> str:
    """Ask the LLM for a verdict JSON based on accumulated scores."""
    system = load_judge_system(agent._motion, retry_note=agent._verdict_fail)
    history = "\n".join(f"{s.for_role} r{s.round}: {s.score}" for s in agent._scores[-20:])
    _log("verdict_request", f"scores={len(agent._scores)}")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (f"Debate scores:\n{history}\nReturn final verdict JSON."),
        },
    ]
    estimate = agent.gk.build_estimate(
        messages,
        agent.cfg.judge_model,
        tokens_out=agent.cfg.max_tokens_for_verdict,
    )
    result = agent.gk.execute(
        lambda: agent.llm.chat(messages, agent.cfg.max_tokens_for_verdict),
        estimate=estimate,
        role="judge",
        turn_id=agent._turn_id,
        model=agent.cfg.judge_model,
    )
    return result.text


def log_verdict(agent: JudgeAgent, verdict: VerdictPayload) -> None:
    agent.logger.event(
        "verdict",
        role="judge",
        turn_id=agent._turn_id,
        data=verdict.model_dump(mode="json"),
    )
    _log("verdict_logged", f"winner={verdict.winner}")


def aborted_verdict(agent: JudgeAgent) -> VerdictPayload:
    reason = agent._ctx.abort_reason or "aborted"
    agent.logger.event(
        "verdict",
        role="judge",
        turn_id=agent._turn_id,
        data={
            "outcome": reason,
            "round": agent._ctx.round,
            "turn": agent._turn_id,
        },
    )
    return VerdictPayload(
        winner="con",
        reasons=[
            f"Debate aborted: {reason} — default outcome applied.",
            "Transcript preserved for review per recovery semantics.",
            "No validated LLM verdict was produced before abort.",
        ],
        scores=VerdictScores(pro=0.0, con=1.0),
    )


def emit_abort(agent: JudgeAgent, name: str, *, detail: str = "") -> None:
    agent.logger.event(
        name,
        role="judge",
        turn_id=agent._turn_id,
        data={"detail": detail},
    )
    agent._ctx.abort_reason = name


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    write_diag_line(msg)
