"""Batched round evaluation skill (score Pro + Con + summary in one LLM call)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from debate.sdk.payloads import ScorePayload
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.skills_proto import LLMClientProto

_ROUND_EVAL_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def make_round_eval_skill(
    client: LLMClientProto,
    gk: Gatekeeper,
    *,
    system_prompt: str,
    model: str,
) -> Callable[[dict[str, Any]], tuple[ScorePayload, ScorePayload, str]]:
    """Single LLM call: score Pro, score Con, and round summary (batched)."""

    def skill(args: dict[str, Any]) -> tuple[ScorePayload, ScorePayload, str]:
        text = str(args["text"])
        round_id = int(args["round"])
        turn_id = int(args.get("turn_id", round_id))
        max_out = gk.cfg.round_eval_max_tokens
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        estimate = gk.build_estimate(messages, model, tokens_out=max_out)
        result = gk.execute(
            lambda: client.chat(
                messages,
                max_out,
                response_format={"type": "json_object"},
            ),
            estimate=estimate,
            role="judge",
            turn_id=turn_id,
            model=model,
        )
        return _parse_round_eval_json(result.text, round_id=round_id)

    return skill


def _parse_round_eval_json(text: str, *, round_id: int) -> tuple[ScorePayload, ScorePayload, str]:
    cleaned = text.strip()
    match = _ROUND_EVAL_JSON_FENCE.search(cleaned)
    blob = match.group(1).strip() if match else cleaned
    decoder = json.JSONDecoder()
    idx = blob.find("{")
    if idx < 0:
        msg = "no JSON object in round_eval reply"
        raise ValueError(msg)
    try:
        data, _end = decoder.raw_decode(blob, idx)
    except json.JSONDecodeError as exc:
        msg = f"round_eval JSON parse error: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(data, dict):
        msg = "round_eval JSON must be an object"
        raise TypeError(msg)
    pro_raw = data.get("pro")
    con_raw = data.get("con")
    summary = str(data.get("summary", "")).strip()
    if not isinstance(pro_raw, dict) or not isinstance(con_raw, dict):
        msg = "round_eval requires pro and con objects"
        raise ValueError(msg)
    pro_sp = _side_payload_from_dict(pro_raw, for_role="pro", round_id=round_id)
    con_sp = _side_payload_from_dict(con_raw, for_role="con", round_id=round_id)
    if not summary:
        summary = "Round summary unavailable."
    return pro_sp, con_sp, summary


def _side_payload_from_dict(raw: dict[str, Any], *, for_role: str, round_id: int) -> ScorePayload:
    score_val = raw.get("score", 0.0)
    try:
        score = float(score_val)
    except (TypeError, ValueError):
        score = 0.0
    pts = raw.get("points", [])
    points: list[str] = []
    if isinstance(pts, list):
        for p in pts:
            if isinstance(p, str) and p.strip():
                points.append(p.strip())
    if not points:
        points = ["evaluated in batch"]
    return ScorePayload(for_role=for_role, round=round_id, points=points, score=score)
