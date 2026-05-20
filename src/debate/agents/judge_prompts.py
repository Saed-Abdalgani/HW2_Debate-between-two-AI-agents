"""Load judge-facing prompt templates from config/prompts.

Includes template validation, prompt caching, length checking,
motion sanitisation, and rich retry-note formatting.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS = _ROOT / "config" / "prompts"

# Required template files.
_JUDGE_TEMPLATE = _PROMPTS / "judge.system.txt"
_SCORE_RUBRIC = _PROMPTS / "score.rubric.txt"
_SUMMARISE_TEMPLATE = _PROMPTS / "summarise.system.txt"

# Module-level cache to avoid repeated disk I/O.
_cache: dict[str, str] = {}

# Validation.
_MAX_PROMPT_LENGTH = 10_000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LOG_PREFIX = "[PROMPTS]"


def validate_prompt_files() -> None:
    """Verify all required prompt template files exist."""
    missing: list[str] = []
    for path in (_JUDGE_TEMPLATE, _SCORE_RUBRIC, _SUMMARISE_TEMPLATE):
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError(f"missing prompt templates: {', '.join(missing)}")


def validate_template_placeholders(template: str, required: set[str]) -> list[str]:
    """Return list of missing placeholders in a template."""
    missing = []
    for placeholder in required:
        token = "{" + placeholder + "}"
        if token not in template:
            missing.append(placeholder)
    return missing


def _read_cached(path: Path) -> str:
    """Read a file, caching in memory for subsequent calls."""
    key = str(path)
    if key not in _cache:
        _cache[key] = path.read_text(encoding="utf-8")
    return _cache[key]


def clear_cache() -> None:
    """Clear the template cache (useful in tests)."""
    _cache.clear()


def _sanitise_for_template(text: str) -> str:
    """Strip control chars from text before template insertion."""
    return _CONTROL_CHARS.sub("", text).strip()


def load_judge_system(motion: str, *, retry_note: str = "") -> str:
    """Load and compose the judge system prompt."""
    template = _read_cached(_JUDGE_TEMPLATE)
    missing = validate_template_placeholders(template, {"motion", "retry_note"})
    if missing:
        _log("template_warning", f"missing placeholders: {missing}")
    clean_motion = _sanitise_for_template(motion)
    note = retry_note.strip()
    if note:
        note = f"Previous verdict was invalid: {note}\nFix all issues and return valid JSON only."
    prompt = template.format(motion=clean_motion, retry_note=note)
    if len(prompt) > _MAX_PROMPT_LENGTH:
        _log(
            "prompt_too_long",
            f"len={len(prompt)} max={_MAX_PROMPT_LENGTH}",
        )
    return prompt


def load_score_rubric() -> str:
    """Load the scoring rubric template."""
    rubric = _read_cached(_SCORE_RUBRIC)
    if not rubric.strip():
        _log("rubric_empty", "score.rubric.txt is empty")
    return rubric


def load_summarise_system() -> str:
    """Load the summarisation system prompt."""
    template = _read_cached(_SUMMARISE_TEMPLATE)
    if not template.strip():
        _log("summarise_empty", "summarise.system.txt is empty")
    return template


def load_verdict_schema() -> str:
    """Load the verdict JSON schema for reference."""
    schema_path = _PROMPTS / "verdict.schema.json"
    if not schema_path.exists():
        _log("schema_missing", "verdict.schema.json not found")
        return "{}"
    return _read_cached(schema_path)


def prompt_stats(text: str) -> dict[str, int]:
    """Return basic statistics about a prompt string."""
    lines = text.strip().splitlines()
    words = text.split()
    return {
        "chars": len(text),
        "lines": len(lines),
        "words": len(words),
    }

def detect_prompt_injection(motion: str) -> bool:
    """Quick check for common prompt-injection phrases."""
    lowered = motion.lower()
    dangerous = [
        "ignore previous",
        "disregard above",
        "override rules",
        "reveal system prompt",
        "you are now",
    ]
    return any(phrase in lowered for phrase in dangerous)

def format_retry_note(raw_note: str) -> str:
    """Build a structured retry note from a raw failure description."""
    note = raw_note.strip()
    if not note:
        return ""
    parts = [
        f"Previous verdict was invalid: {note}",
        "Fix all issues listed above.",
        "Return valid JSON only — no markdown fences.",
    ]
    return "\n".join(parts)

def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")