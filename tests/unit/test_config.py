"""Unit tests for config loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from config_test_data import VALID_DEBATE_CONFIG as _VALID
from config_test_data import write_json as _write

from debate.shared.config import ConfigError, load_config


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
def test_llm_model_env_overrides_all_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "debate.json"
    _write(path, _VALID)
    monkeypatch.setenv("LLM_MODEL", "llama3-8b-8192")
    cfg = load_config(path)
    assert cfg.model == "llama-3.1-8b-instant"
    assert cfg.score_model == "llama-3.1-8b-instant"
    assert cfg.judge_model == "llama-3.1-8b-instant"


@pytest.mark.unit
def test_groq_legacy_json_models_remapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "debate.json"
    custom = dict(_VALID)
    custom["model"] = custom["score_model"] = custom["judge_model"] = "llama3-70b-8192"
    _write(path, custom)
    monkeypatch.setenv("LLM_MODEL", "")
    cfg = load_config(path)
    assert cfg.model == "llama-3.3-70b-versatile"
    assert cfg.score_model == "llama-3.3-70b-versatile"
    assert cfg.judge_model == "llama-3.3-70b-versatile"


@pytest.mark.unit
def test_llm_model_env_empty_uses_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "debate.json"
    custom = dict(_VALID)
    custom["model"] = custom["score_model"] = custom["judge_model"] = "from-json"
    _write(path, custom)
    monkeypatch.setenv("LLM_MODEL", "")
    cfg = load_config(path)
    assert cfg.model == "from-json"


@pytest.mark.unit
def test_debate_config_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "override.json"
    custom = dict(_VALID)
    custom["model"] = "custom-model"
    _write(path, custom)
    monkeypatch.setenv("DEBATE_CONFIG", str(path))
    cfg = load_config()
    assert cfg.model == "custom-model"
