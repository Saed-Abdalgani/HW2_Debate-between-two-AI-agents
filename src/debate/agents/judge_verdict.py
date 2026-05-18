"""Multi-stage verdict validation (schema → semantic → consistency)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from debate.sdk.payloads import VerdictPayload
from debate.sdk.schemas import VerdictValidationError, validate_verdict

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass(frozen=True)
class VerdictCheck:
    ok: bool
    verdict: VerdictPayload | None = None
    stage: str = ""
    reason: str = ""


def extract_verdict_dict(text: str) -> dict:
    """Parse JSON from raw LLM text (optional markdown fence)."""
    stripped = text.strip()
    match = _JSON_FENCE.search(stripped)
    blob = match.group(1).strip() if match else stripped
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        raise VerdictValidationError("no JSON object in verdict reply")
    return json.loads(blob[start : end + 1])


def jaccard_similarity(a: str, b: str) -> float:
    sa = {w.lower() for w in re.findall(r"\w+", a)}
    sb = {w.lower() for w in re.findall(r"\w+", b)}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check_semantic(verdict: VerdictPayload) -> str | None:
    if len(verdict.reasons) < 3:
        return "fewer than three reasons"
    for i, left in enumerate(verdict.reasons):
        for right in verdict.reasons[i + 1 :]:
            if jaccard_similarity(left, right) >= 0.9:
                return "duplicate reasons (Jaccard >= 0.9)"
    return None


def check_consistency(verdict: VerdictPayload) -> str | None:
    if verdict.scores.pro == verdict.scores.con:
        return "scores tied"
    if verdict.winner == "pro" and verdict.scores.pro < verdict.scores.con:
        return "winner pro but con score higher"
    if verdict.winner == "con" and verdict.scores.con < verdict.scores.pro:
        return "winner con but pro score higher"
    return None


def validate_verdict_stages(raw_text: str) -> VerdictCheck:
    try:
        data = extract_verdict_dict(raw_text)
    except (json.JSONDecodeError, VerdictValidationError) as exc:
        return VerdictCheck(ok=False, stage="schema", reason=str(exc))
    try:
        verdict = validate_verdict(data)
    except VerdictValidationError as exc:
        return VerdictCheck(ok=False, stage="schema", reason=str(exc))
    reason = check_semantic(verdict)
    if reason:
        return VerdictCheck(ok=False, stage="semantic", reason=reason, verdict=verdict)
    reason = check_consistency(verdict)
    if reason:
        return VerdictCheck(ok=False, stage="consistency", reason=reason, verdict=verdict)
    return VerdictCheck(ok=True, verdict=verdict)
