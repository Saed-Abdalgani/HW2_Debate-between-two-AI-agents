"""P6.6 — agents must not access SEARCH_API_KEY (Judge-proxied search only)."""

from __future__ import annotations

from pathlib import Path

import pytest

_AGENTS_DIR = Path(__file__).resolve().parents[2] / "src" / "debate" / "agents"


@pytest.mark.unit
def test_agents_never_request_search_key() -> None:
    for path in _AGENTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "SEARCH_API_KEY" not in text, f"{path.name} references SEARCH_API_KEY"
        assert 'get_key("SEARCH' not in text


@pytest.mark.unit
def test_agents_no_print_calls() -> None:
    for path in _AGENTS_DIR.glob("*.py"):
        assert "print(" not in path.read_text(encoding="utf-8"), f"{path.name} uses print()"
