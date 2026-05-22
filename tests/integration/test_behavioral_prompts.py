"""Behavioral tests — prompt policy (echo chamber, judge no-draw)."""

from __future__ import annotations

import pytest

from debate.agents.debater_agent import load_debater_system
from debate.agents.judge_prompts import load_judge_system


@pytest.mark.unit
def test_1_echo_chamber_con_prompt_pass() -> None:
    """PASS: Con system text obligates rebuttal even against persuasive Pro."""
    text = load_debater_system("con", "National AI safety boards should be mandatory")
    lowered = text.lower()
    assert "genuine rebuttal" in lowered
    assert "do not agree" in lowered


@pytest.mark.unit
def test_judge_prompt_dead_heat_language_pass() -> None:
    """PASS: Judge template encodes no-draw / weak-symmetric obligation."""
    jp = load_judge_system("Example motion for testing")
    low = jp.lower()
    assert "never declare a tie" in low
    assert "similarly thin" in low or "symmetrically" in low
