"""Load debate.json with .env overlay; fail fast on aggregated validation errors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from debate.shared.config_model import Config, ConfigError, SearchConfig
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
        "round_eval_max_tokens",
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
_GROQ_LEGACY_MODEL_IDS: dict[str, str] = {
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "llama3-70b-8192": "llama-3.3-70b-versatile",
}


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


def _apply_llm_model_env(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)
    raw = get_env("LLM_MODEL")
    if raw is None or not raw.strip():
        return merged
    model = raw.strip()
    merged["model"] = model
    merged["score_model"] = model
    merged["judge_model"] = model
    return merged


def _remap_groq_decommissioned_models(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in ("model", "score_model", "judge_model"):
        name = out.get(key)
        if not isinstance(name, str):
            continue
        replacement = _GROQ_LEGACY_MODEL_IDS.get(name)
        if replacement is not None:
            out[key] = replacement
    return out


def _validate(data: dict[str, Any]) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        issues = [
            f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        raise ConfigError(issues) from exc


def load_config(path: Path | None = None) -> Config:
    load_dotenv(_ENV_FILE, override=False)
    cfg_path = Path(get_env("DEBATE_CONFIG", str(path or DEFAULT_CONFIG_PATH)))
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    merged = _apply_llm_model_env(_apply_env_overrides(raw))
    return _validate(_remap_groq_decommissioned_models(merged))


__all__ = ["Config", "ConfigError", "SearchConfig", "load_config"]
