"""Debater system prompt template, TOOL:search parsing, and safety filters.

Provides input sanitisation, injection detection, and prompt validation
to harden debater agents against adversarial or malformed motions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parents[3]
_DEBATER_PROMPT = _ROOT / "config" / "prompts" / "debater.system.txt"
TOOL_PREFIX = "TOOL:search:"
Stance = Literal["pro", "con"]

# Maximum lengths to prevent resource exhaustion.
MAX_MOTION_LENGTH = 1000
MAX_PROMPT_LENGTH = 8000
MAX_TOOL_QUERY_LENGTH = 300

# Patterns that indicate prompt-injection or social-engineering attempts.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(prior|above)", re.IGNORECASE),
    re.compile(r"override\s+(safety|rules|instructions)", re.IGNORECASE),
]

# Characters that should never appear in a motion string.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitise_motion(motion: str) -> str:
    """Strip control characters and validate motion length."""
    cleaned = _CONTROL_CHARS.sub("", motion).strip()
    if not cleaned:
        raise ValueError("motion must not be empty after sanitisation")
    if len(cleaned) > MAX_MOTION_LENGTH:
        raise ValueError(f"motion exceeds {MAX_MOTION_LENGTH} chars (got {len(cleaned)})")
    return cleaned


def detect_injection(text: str) -> str | None:
    """Return the matched injection pattern name, or ``None`` if safe."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def validate_stance(stance: str) -> Stance:
    """Ensure stance is exactly 'pro' or 'con'."""
    if stance not in ("pro", "con"):
        raise ValueError(f"invalid stance {stance!r}; must be 'pro' or 'con'")
    return stance  # type: ignore[return-value]


def load_debater_system(stance: str, motion: str) -> str:
    """Load and compose the debater system prompt with safety checks."""
    validated_stance = validate_stance(stance)
    clean_motion = sanitise_motion(motion)
    injection = detect_injection(clean_motion)
    if injection:
        _log_safety("injection_detected", stance, injection)
        clean_motion = "(motion redacted — injection attempt detected)"
    if not _DEBATER_PROMPT.exists():
        raise FileNotFoundError(f"debater prompt template not found: {_DEBATER_PROMPT}")
    template = _DEBATER_PROMPT.read_text(encoding="utf-8")
    prompt = template.format(stance=validated_stance, motion=clean_motion)
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"composed prompt exceeds {MAX_PROMPT_LENGTH} chars (got {len(prompt)})")
    return prompt


def parse_tool_query(text: str) -> str | None:
    """Extract a TOOL:search query from the first line, if present."""
    line = text.strip().split("\n", 1)[0]
    if not line.startswith(TOOL_PREFIX):
        return None
    query = line[len(TOOL_PREFIX) :].strip()
    if not query:
        return None
    return _sanitise_tool_query(query)


def validate_tool_response(text: str) -> list[str]:
    """Return all TOOL:search lines found (should be at most one)."""
    lines = text.strip().splitlines()
    return [ln for ln in lines if ln.strip().startswith(TOOL_PREFIX)]


def scan_reply_safety(text: str) -> list[str]:
    """Scan an LLM reply for safety violations. Returns warnings."""
    warnings: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            warnings.append(f"injection pattern in reply: {pattern.pattern}")
    tool_lines = validate_tool_response(text)
    if len(tool_lines) > 1:
        warnings.append(f"multiple TOOL lines in single reply ({len(tool_lines)})")
    return warnings


def motion_complexity(motion: str) -> dict[str, int]:
    """Return basic complexity metrics for a motion string."""
    words = motion.split()
    sentences = [s for s in motion.split(".") if s.strip()]
    return {
        "chars": len(motion),
        "words": len(words),
        "sentences": len(sentences),
    }


def _sanitise_tool_query(query: str) -> str:
    """Clamp query length and strip dangerous characters."""
    cleaned = _CONTROL_CHARS.sub("", query).strip()
    if len(cleaned) > MAX_TOOL_QUERY_LENGTH:
        cleaned = cleaned[:MAX_TOOL_QUERY_LENGTH]
    return cleaned


def _log_safety(event: str, stance: str, detail: str) -> None:
    """Emit a safety event to stderr for audit purposes."""
    sys.stderr.write(f"[SAFETY] debater_prompt {event}: stance={stance} detail={detail[:120]}\n")
