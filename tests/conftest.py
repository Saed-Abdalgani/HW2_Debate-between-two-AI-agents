"""Pytest hooks — keep tests deterministic when developers have a local ``.env``."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _shield_llm_env_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """``load_dotenv(override=False)`` skips keys already in ``os.environ``.

    A repo-root ``.env`` may set ``LLM_MODEL`` / ``LLM_BASE_URL`` for Groq; unit tests
    expect ``config/debate.json`` defaults and OpenAI pricing mocks unless they override.
    """
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
