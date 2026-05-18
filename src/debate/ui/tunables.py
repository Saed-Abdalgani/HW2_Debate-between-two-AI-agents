"""In-memory config edits for the menu session (P8.1)."""

from __future__ import annotations

from debate.shared.config import Config


def apply_rounds(cfg: Config, value: str) -> str | None:
    try:
        n = int(value)
    except ValueError:
        return "rounds must be an integer"
    if n < 1:
        return "rounds must be at least 1"
    cfg.rounds = n
    return None


def apply_max_tokens(cfg: Config, value: str) -> str | None:
    try:
        n = int(value)
    except ValueError:
        return "max_tokens_per_turn must be an integer"
    if n < 1:
        return "max_tokens_per_turn must be at least 1"
    cfg.max_tokens_per_turn = n
    return None


def apply_budget_usd(cfg: Config, value: str) -> str | None:
    try:
        x = float(value)
    except ValueError:
        return "budget must be a number"
    if x <= 0:
        return "budget must be positive"
    cfg.max_usd_per_debate = x
    return None


def apply_model(cfg: Config, value: str) -> str | None:
    if not value.strip():
        return "model cannot be empty"
    cfg.model = value.strip()
    cfg.judge_model = cfg.model
    cfg.score_model = cfg.model
    return None
