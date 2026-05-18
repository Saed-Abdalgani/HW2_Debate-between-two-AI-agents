"""Integration — debater child env must not receive search API keys (P6.5)."""

from __future__ import annotations

import pytest
from debater_stub_helpers import stub_env

from debate.orchestration.supervisor import Supervisor
from debate.shared.config import load_config


@pytest.fixture
def cfg():
    return load_config()


@pytest.mark.integration
def test_supervisor_strips_search_key(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_env(monkeypatch)
    monkeypatch.setenv("SEARCH_API_KEY", "must-not-reach-child")
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    try:
        sup.spawn("pro")
        stderr_path = tmp_path / "stderr" / "pro.stderr.log"
        sup.terminate("pro")
    finally:
        sup.shutdown_all()
    assert not stderr_path.exists() or "must-not-reach-child" not in stderr_path.read_text(
        encoding="utf-8", errors="ignore"
    )
    child = sup._safe_child_env()
    assert "SEARCH_API_KEY" not in child


@pytest.mark.integration
def test_child_env_has_no_search_key(cfg, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub_env(monkeypatch)
    monkeypatch.setenv("SEARCH_API_KEY", "stripped")
    sup = Supervisor(cfg, stderr_dir=tmp_path / "stderr")
    env = sup._safe_child_env()
    assert "SEARCH_API_KEY" not in env
    assert "LLM_API_KEY" in env
