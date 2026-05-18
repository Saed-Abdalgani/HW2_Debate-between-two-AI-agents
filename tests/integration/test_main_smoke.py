"""Integration — non-interactive main with stub LLM (P8.5)."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.integration
def test_main_non_interactive_exits_zero() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "debate.main",
            "--non-interactive",
            "--rounds",
            "1",
            "--stub",
            "--motion",
            "AI helps humanity in the next decade.",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={
            **__import__("os").environ,
            "PYTHONUNBUFFERED": "1",
            "LLM_API_KEY": "test-key-not-used",
        },
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Winner:" in proc.stdout
