"""Unit tests for secrets vault."""

from __future__ import annotations

import pytest

from debate.shared.secrets import MissingSecretError, get_env, get_key, redact


@pytest.mark.unit
def test_get_key_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(MissingSecretError) as exc:
        get_key("LLM_API_KEY")
    assert exc.value.name == "LLM_API_KEY"
    assert "sk-" not in str(exc.value)


@pytest.mark.unit
def test_get_key_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-testkey12345678901234567890")
    assert get_key("LLM_API_KEY").startswith("sk-")


@pytest.mark.unit
def test_get_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEBATE_CONFIG", raising=False)
    assert get_env("DEBATE_CONFIG") is None
    assert get_env("DEBATE_CONFIG", "x") == "x"


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        "LLM_API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
        "SEARCH_API_KEY=abc1234567890",
        "token sk-abcdefghijklmnopqrstuvwxyz here",
        "Authorization: Bearer secret.token.value",
    ],
)
def test_redact_masks_patterns(payload: str) -> None:
    out = redact(payload)
    assert "sk-" not in out
    assert "Bearer secret" not in out
    assert "***REDACTED***" in out


@pytest.mark.unit
def test_redact_dict_masks_secret_keys() -> None:
    out = redact({"LLM_API_KEY": "sk-leak", "note": "ok"})
    assert out["LLM_API_KEY"] == "***REDACTED***"
    assert out["note"] == "ok"


@pytest.mark.unit
def test_redact_is_idempotent() -> None:
    raw = "LLM_API_KEY=sk-abcdefghijklmnopqrstuvwxyz"
    once = redact(raw)
    twice = redact(once)
    assert once == twice
