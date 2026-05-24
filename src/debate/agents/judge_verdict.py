"""Multi-stage verdict validation (schema → semantic → consistency).

Includes deeper semantic checks, score range validation, winner-reason
alignment verification, Unicode safety, and structured validation logging.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from debate.sdk.payloads import VerdictPayload
from debate.sdk.schemas import VerdictValidationError, validate_verdict
from debate.shared.diag_log import write_diag_line

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Validation thresholds.
_MIN_REASON_LENGTH = 20
_MIN_REASON_COUNT = 3
_JACCARD_DUPLICATE_THRESHOLD = 0.9
_SCORE_MIN = 0.0
_SCORE_MAX = 100.0
_LOG_PREFIX = "[VERDICT]"


@dataclass(frozen=True)
class VerdictCheck:
    """Result of multi-stage verdict validation."""

    ok: bool
    verdict: VerdictPayload | None = None
    stage: str = ""
    reason: str = ""


def normalise_verdict_text(text: str) -> str:
    """Strip control characters and common LLM formatting quirks."""
    cleaned = _CONTROL_CHARS.sub("", text).strip()
    # Some LLMs wrap JSON in extra quotes or backticks.
    if cleaned.startswith("'") and cleaned.endswith("'"):
        cleaned = cleaned[1:-1]
    return cleaned


def extract_verdict_dict(text: str) -> dict:
    """Parse JSON from raw LLM text (optional markdown fence)."""
    stripped = normalise_verdict_text(text)
    match = _JSON_FENCE.search(stripped)
    blob = match.group(1).strip() if match else stripped
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        raise VerdictValidationError("no JSON object in verdict reply")
    return json.loads(blob[start : end + 1])


def jaccard_similarity(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    sa = {w.lower() for w in re.findall(r"\w+", a)}
    sb = {w.lower() for w in re.findall(r"\w+", b)}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check_semantic(verdict: VerdictPayload) -> str | None:
    """Validate reason count, length, and uniqueness."""
    if len(verdict.reasons) < _MIN_REASON_COUNT:
        return f"fewer than {_MIN_REASON_COUNT} reasons"
    for i, reason in enumerate(verdict.reasons):
        if len(reason.strip()) < _MIN_REASON_LENGTH:
            return f"reason {i + 1} too short ({len(reason.strip())} < {_MIN_REASON_LENGTH} chars)"
    for i, left in enumerate(verdict.reasons):
        for right in verdict.reasons[i + 1 :]:
            sim = jaccard_similarity(left, right)
            if sim >= _JACCARD_DUPLICATE_THRESHOLD:
                return f"duplicate reasons (Jaccard {sim:.2f} >= {_JACCARD_DUPLICATE_THRESHOLD})"
    return None


def check_consistency(verdict: VerdictPayload) -> str | None:
    """Validate score-winner alignment and score ranges."""
    pro, con = verdict.scores.pro, verdict.scores.con
    if not (_SCORE_MIN <= pro <= _SCORE_MAX):
        return f"pro score {pro} out of [{_SCORE_MIN}, {_SCORE_MAX}]"
    if not (_SCORE_MIN <= con <= _SCORE_MAX):
        return f"con score {con} out of [{_SCORE_MIN}, {_SCORE_MAX}]"
    if pro == con:
        return "scores tied"
    if verdict.winner == "pro" and pro < con:
        return "winner pro but con score higher"
    if verdict.winner == "con" and con < pro:
        return "winner con but pro score higher"
    return None


def validate_verdict_stages(raw_text: str) -> VerdictCheck:
    """Run schema → semantic → consistency checks in order."""
    _log("validating", f"len={len(raw_text)}")
    try:
        data = extract_verdict_dict(raw_text)
    except (json.JSONDecodeError, VerdictValidationError) as exc:
        _log("schema_fail", str(exc)[:80])
        return VerdictCheck(ok=False, stage="schema", reason=str(exc))
    try:
        verdict = validate_verdict(data)
    except VerdictValidationError as exc:
        _log("schema_fail", str(exc)[:80])
        return VerdictCheck(ok=False, stage="schema", reason=str(exc))
    reason = check_semantic(verdict)
    if reason:
        _log("semantic_fail", reason)
        return VerdictCheck(ok=False, stage="semantic", reason=reason, verdict=verdict)
    reason = check_consistency(verdict)
    if reason:
        _log("consistency_fail", reason)
        return VerdictCheck(ok=False, stage="consistency", reason=reason, verdict=verdict)
    _log("valid", f"winner={verdict.winner}")
    return VerdictCheck(ok=True, verdict=verdict)


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    write_diag_line(msg)
