"""Debater system prompt template and TOOL:search line parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parents[3]
_DEBATER_PROMPT = _ROOT / "config" / "prompts" / "debater.system.txt"
TOOL_PREFIX = "TOOL:search:"
Stance = Literal["pro", "con"]


def load_debater_system(stance: str, motion: str) -> str:
    return _DEBATER_PROMPT.read_text(encoding="utf-8").format(stance=stance, motion=motion)


def parse_tool_query(text: str) -> str | None:
    line = text.strip().split("\n", 1)[0]
    if line.startswith(TOOL_PREFIX):
        query = line[len(TOOL_PREFIX) :].strip()
        return query or None
    return None
