"""Unit tests for config loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from debate.shared.config import ConfigError, load_config

_VALID = {
    "rounds": 10,
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens_per_turn": 800,
    "max_tokens_per_debate": 60000,
    "max_usd_per_debate": 1.5,
    "max_requests_per_minute": 30,
    "heartbeat_sec": 5,
    "heartbeat_timeout_sec": 3,
    "heartbeat_max_consecutive_misses": 2,
    "child_terminate_grace_sec": 2,
    "recv_default_timeout_sec": 30,
    "max_restarts_per_child": 2,
    "max_message_bytes": 65536,
    "max_clock_skew_sec": 300,
    "max_retries": 3,
    "retry_initial_delay_sec": 0.25,
    "retry_jitter_sec": 0.05,
    "token_drift_warn_threshold": 0.2,
    "summary_max_tokens": 512,
    "search_cache_max_entries": 128,
    "score_model": "gpt-4o-mini",
    "judge_model": "gpt-4o-mini",
    "http_timeout_sec": 30,
    "search_snippet_max_chars": 500,
    "max_tool_calls_per_turn": 2,
    "search": {"provider": "tavily", "max_results": 5, "cache": True},
}


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.unit
def test_load_default_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEBATE_CONFIG", raising=False)
    monkeypatch.delenv("DEBATE_ROUNDS", raising=False)
    cfg = load_config()
    assert cfg.rounds == 10
    assert cfg.search.provider == "tavily"


@pytest.mark.unit
def test_load_valid_custom_path(tmp_path: Path) -> None:
    path = tmp_path / "debate.json"
    _write(path, _VALID)
    cfg = load_config(path)
    assert cfg.model == "gpt-4o-mini"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mutator", "needle"),
    [
        (lambda d: d | {"rounds": 0}, "rounds"),
        (lambda d: d | {"temperature": 3}, "temperature"),
        (lambda d: d | {"max_usd_per_debate": 0}, "max_usd_per_debate"),
        (lambda d: d | {"max_tokens_per_turn": 0}, "max_tokens_per_turn"),
    ],
)
def test_reject_bad_ranges(tmp_path: Path, mutator, needle: str) -> None:
    path = tmp_path / "bad.json"
    _write(path, mutator(dict(_VALID)))
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert needle in str(exc.value)


@pytest.mark.unit
def test_aggregated_validation_errors(tmp_path: Path) -> None:
    path = tmp_path / "multi.json"
    _write(path, _VALID | {"rounds": 0, "temperature": 9, "max_usd_per_debate": -1})
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert len(exc.value.issues) >= 3


@pytest.mark.unit
def test_reject_unknown_top_level_key(tmp_path: Path) -> None:
    path = tmp_path / "extra.json"
    _write(path, _VALID | {"surprise": True})
    with pytest.raises(ConfigError):
        load_config(path)


@pytest.mark.unit
def test_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "debate.json"
    _write(path, _VALID)
    monkeypatch.setenv("DEBATE_ROUNDS", "3")
    cfg = load_config(path)
    assert cfg.rounds == 3


@pytest.mark.unit
def test_invalid_env_override_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "debate.json"
    _write(path, _VALID)
    monkeypatch.setenv("DEBATE_ROUNDS", "not-a-number")
    with pytest.raises(ConfigError, match="DEBATE_ROUNDS"):
        load_config(path)


@pytest.mark.unit
def test_debate_config_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "override.json"
    custom = dict(_VALID)
    custom["model"] = "custom-model"
    _write(path, custom)
    monkeypatch.setenv("DEBATE_CONFIG", str(path))
    cfg = load_config()
    assert cfg.model == "custom-model"
