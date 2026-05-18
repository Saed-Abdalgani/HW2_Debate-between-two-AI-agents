"""Load debate.json with .env overlay; fail fast with aggregated validation errors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from debate.shared.secrets import get_env

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _ROOT / "config" / "debate.json"
_ENV_FILE = _ROOT / ".env"
_ENV_OVERRIDES: dict[str, str] = {
    "DEBATE_ROUNDS": "rounds",
    "DEBATE_MODEL": "model",
    "DEBATE_TEMPERATURE": "temperature",
    "DEBATE_MAX_USD_PER_DEBATE": "max_usd_per_debate",
}
_INT_KEYS = frozenset(
    {
        "rounds",
        "max_tokens_per_turn",
        "max_tokens_per_debate",
        "max_requests_per_minute",
        "max_restarts_per_child",
        "max_message_bytes",
        "max_retries",
        "summary_max_tokens",
        "search_cache_max_entries",
        "search_snippet_max_chars",
        "heartbeat_max_consecutive_misses",
        "max_tool_calls_per_turn",
        "max_tokens_for_verdict",
    }
)
_FLOAT_KEYS = frozenset(
    {
        "temperature",
        "max_usd_per_debate",
        "heartbeat_sec",
        "heartbeat_timeout_sec",
        "max_clock_skew_sec",
        "retry_initial_delay_sec",
        "retry_jitter_sec",
        "token_drift_warn_threshold",
        "http_timeout_sec",
        "child_terminate_grace_sec",
        "recv_default_timeout_sec",
    }
)


class ConfigError(Exception):
    """All validation failures from a single load attempt."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


class SearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1)
    max_results: int = Field(ge=1, le=50)
    cache: bool


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rounds: int = Field(ge=1)
    model: str = Field(min_length=1)
    temperature: float = Field(gt=0, le=2)
    max_tokens_per_turn: int = Field(ge=1)
    max_tokens_per_debate: int = Field(ge=1)
    max_usd_per_debate: float = Field(gt=0)
    max_requests_per_minute: int = Field(ge=1)
    heartbeat_sec: float = Field(gt=0)
    heartbeat_timeout_sec: float = Field(gt=0)
    heartbeat_max_consecutive_misses: int = Field(ge=1)
    child_terminate_grace_sec: float = Field(gt=0)
    recv_default_timeout_sec: float = Field(gt=0)
    max_restarts_per_child: int = Field(ge=0)
    max_message_bytes: int = Field(ge=1)
    max_clock_skew_sec: float = Field(ge=0)
    max_retries: int = Field(ge=0)
    retry_initial_delay_sec: float = Field(ge=0)
    retry_jitter_sec: float = Field(ge=0)
    token_drift_warn_threshold: float = Field(ge=0, le=1)
    summary_max_tokens: int = Field(ge=1)
    search_cache_max_entries: int = Field(ge=1)
    score_model: str = Field(min_length=1)
    judge_model: str = Field(min_length=1)
    http_timeout_sec: float = Field(gt=0)
    search_snippet_max_chars: int = Field(ge=1)
    max_tool_calls_per_turn: int = Field(ge=0, default=2)
    max_tokens_for_verdict: int = Field(ge=1, default=1200)
    search: SearchConfig


def _parse_env_value(key: str, raw: str) -> Any:
    if key in _INT_KEYS:
        return int(raw)
    if key in _FLOAT_KEYS:
        return float(raw)
    return raw


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    issues: list[str] = []
    for env_name, field in _ENV_OVERRIDES.items():
        raw = get_env(env_name)
        if raw is None:
            continue
        try:
            merged[field] = _parse_env_value(field, raw)
        except ValueError:
            issues.append(f"{env_name}: invalid value {raw!r}")
    if issues:
        raise ConfigError(issues)
    return merged


def _validate(data: dict[str, Any]) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        issues = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        raise ConfigError(issues) from exc


def load_config(path: Path | None = None) -> Config:
    """Load JSON config; overlay .env; env vars win on overlapping tunables."""
    load_dotenv(_ENV_FILE, override=False)
    cfg_path = Path(get_env("DEBATE_CONFIG", str(path or DEFAULT_CONFIG_PATH)))
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _validate(_apply_env_overrides(raw))
