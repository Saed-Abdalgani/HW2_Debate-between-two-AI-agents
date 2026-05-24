"""Load judge-facing prompt templates from config/prompts."""

from __future__ import annotations

import re
from pathlib import Path

from debate.agents.judge_prompts_misc import (
    detect_prompt_injection,
    format_retry_note,
    prompt_stats,
)
from debate.shared.diag_log import write_diag_line

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS = _ROOT / "config" / "prompts"

_JUDGE_TEMPLATE = _PROMPTS / "judge.system.txt"
_SCORE_RUBRIC = _PROMPTS / "score.rubric.txt"
_SUMMARISE_TEMPLATE = _PROMPTS / "summarise.system.txt"

_cache: dict[str, str] = {}

_MAX_PROMPT_LENGTH = 10_000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LOG_PREFIX = "[PROMPTS]"


def validate_prompt_files() -> None:
    missing: list[str] = []
    for path in (_JUDGE_TEMPLATE, _SCORE_RUBRIC, _SUMMARISE_TEMPLATE):
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise FileNotFoundError(f"missing prompt templates: {', '.join(missing)}")


def validate_template_placeholders(template: str, required: set[str]) -> list[str]:
    missing = []
    for placeholder in required:
        token = "{" + placeholder + "}"
        if token not in template:
            missing.append(placeholder)
    return missing


def _read_cached(path: Path) -> str:
    key = str(path)
    if key not in _cache:
        _cache[key] = path.read_text(encoding="utf-8")
    return _cache[key]


def clear_cache() -> None:
    _cache.clear()


def _sanitise_for_template(text: str) -> str:
    return _CONTROL_CHARS.sub("", text).strip()


def load_judge_system(motion: str, *, retry_note: str = "") -> str:
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
        _log("prompt_too_long", f"len={len(prompt)} max={_MAX_PROMPT_LENGTH}")
    return prompt


def load_score_rubric() -> str:
    rubric = _read_cached(_SCORE_RUBRIC)
    if not rubric.strip():
        _log("rubric_empty", "score.rubric.txt is empty")
    return rubric


def load_summarise_system() -> str:
    template = _read_cached(_SUMMARISE_TEMPLATE)
    if not template.strip():
        _log("summarise_empty", "summarise.system.txt is empty")
    return template


def load_verdict_schema() -> str:
    schema_path = _PROMPTS / "verdict.schema.json"
    if not schema_path.exists():
        _log("schema_missing", "verdict.schema.json not found")
        return "{}"
    return _read_cached(schema_path)


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    write_diag_line(msg)


__all__ = [
    "clear_cache",
    "detect_prompt_injection",
    "format_retry_note",
    "load_judge_system",
    "load_score_rubric",
    "load_summarise_system",
    "load_verdict_schema",
    "prompt_stats",
    "validate_prompt_files",
    "validate_template_placeholders",
]
