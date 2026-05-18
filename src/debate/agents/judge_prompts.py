"""Load judge-facing prompt templates from config/prompts."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS = _ROOT / "config" / "prompts"


def load_judge_system(motion: str, *, retry_note: str = "") -> str:
    template = (_PROMPTS / "judge.system.txt").read_text(encoding="utf-8")
    note = retry_note.strip()
    if note:
        note = f"Previous verdict was invalid: {note}\nFix all issues and return valid JSON only."
    return template.format(motion=motion, retry_note=note)


def load_score_rubric() -> str:
    return (_PROMPTS / "score.rubric.txt").read_text(encoding="utf-8")


def load_summarise_system() -> str:
    return (_PROMPTS / "summarise.system.txt").read_text(encoding="utf-8")
