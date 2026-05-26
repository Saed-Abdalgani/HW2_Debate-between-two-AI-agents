"""Built-in Router skills: search, summarise, score, round_eval.

Skill factories dispatch through ``Gatekeeper.execute`` for budget/RPM (P3.4).
``search`` uses cache-hit bypass (P3.6); round-eval lives in ``skills_round_eval``.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from debate.sdk.payloads import ScorePayload, ToolResultPayload
from debate.shared.budget import Usage
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.skills_proto import LLMClientProto, SearchClientProto
from debate.shared.skills_round_eval import make_round_eval_skill

_SEARCH_BILLING_MODEL = "search"


def make_search_skill(
    client: SearchClientProto, gk: Gatekeeper
) -> Callable[[dict[str, Any]], ToolResultPayload]:
    """Wrap a ``SearchClient`` as a Router skill (cache miss path)."""

    def skill(args: dict[str, Any]) -> ToolResultPayload:
        query, k = args["query"], int(args.get("k", gk.cfg.search.max_results))
        turn_id = int(args.get("turn_id", 0))
        hits = gk.execute(
            lambda: client.query(query, k),
            estimate=Usage(usd=Decimal("0"), requests=1),
            role="judge",
            turn_id=turn_id,
            model=_SEARCH_BILLING_MODEL,
        )
        return ToolResultPayload(skill="search", hits=list(hits), cached=False)

    return skill


def make_summarise_skill(
    client: LLMClientProto, gk: Gatekeeper, *, system_prompt: str, model: str
) -> Callable[[dict[str, Any]], str]:
    """Wrap an LLM call with a fixed summarisation system prompt."""

    def skill(args: dict[str, Any]) -> str:
        text = str(args["text"])
        role = str(args.get("role", "judge"))
        turn_id = int(args.get("turn_id", 0))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        estimate = gk.build_estimate(messages, model)
        result = gk.execute(
            lambda: client.chat(messages, gk.cfg.summary_max_tokens),
            estimate=estimate,
            role=role,
            turn_id=turn_id,
            model=model,
        )
        return result.text

    return skill


def make_score_skill(
    client: LLMClientProto, gk: Gatekeeper, *, rubric: str, model: str
) -> Callable[[dict[str, Any]], ScorePayload]:
    """Wrap an LLM call with the scoring rubric; parses a ``ScorePayload``."""

    def skill(args: dict[str, Any]) -> ScorePayload:
        text = str(args["text"])
        for_role = args["for_role"]
        round_id = int(args["round"])
        turn_id = int(args.get("turn_id", round_id))
        messages = [
            {"role": "system", "content": rubric},
            {"role": "user", "content": text},
        ]
        estimate = gk.build_estimate(messages, model)
        result = gk.execute(
            lambda: client.chat(messages, gk.cfg.max_tokens_per_turn),
            estimate=estimate,
            role="judge",
            turn_id=turn_id,
            model=model,
        )
        return _parse_score(result.text, for_role=for_role, round_id=round_id)

    return skill


def _parse_score(text: str, *, for_role: str, round_id: int) -> ScorePayload:
    """Tolerant rubric parser: ``score=<float>`` and ``- <point>`` bullets."""
    score = 0.0
    points: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower().startswith("score="):
            try:
                score = float(line.split("=", 1)[1].strip())
            except ValueError:
                score = 0.0
        elif line.startswith("- "):
            points.append(line[2:].strip())
    return ScorePayload(for_role=for_role, round=round_id, points=points, score=score)


__all__ = [
    "LLMClientProto",
    "SearchClientProto",
    "make_round_eval_skill",
    "make_score_skill",
    "make_search_skill",
    "make_summarise_skill",
]
