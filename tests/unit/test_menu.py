"""Unit tests — menu validation and tunables (P8.5)."""

from __future__ import annotations

import pytest

from debate.shared.config import load_config
from debate.ui.menu import Menu
from debate.ui.tunables import apply_budget_usd, apply_max_tokens, apply_rounds


@pytest.mark.unit
def test_apply_rounds_rejects_bad() -> None:
    cfg = load_config()
    assert apply_rounds(cfg, "-1") is not None
    assert apply_rounds(cfg, "x") is not None
    assert apply_rounds(cfg, "3") is None
    assert cfg.rounds == 3


@pytest.mark.unit
def test_apply_max_tokens_rejects_bad() -> None:
    cfg = load_config()
    assert apply_max_tokens(cfg, "0") is not None
    assert apply_max_tokens(cfg, "100") is None


@pytest.mark.unit
def test_apply_budget_rejects_bad() -> None:
    cfg = load_config()
    assert apply_budget_usd(cfg, "-1") is not None
    assert apply_budget_usd(cfg, "2.5") is None


@pytest.mark.unit
def test_menu_apply_field_unknown() -> None:
    menu = Menu(load_config())
    assert "unknown" in (menu._apply_field("nope", "1") or "")


@pytest.mark.unit
def test_menu_keyboard_interrupt_on_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    menu = Menu(load_config())
    calls = 0

    def ask(*_a, **_k):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt
        return "6"

    monkeypatch.setattr("debate.ui.menu.Prompt.ask", ask)
    menu.run_loop()
