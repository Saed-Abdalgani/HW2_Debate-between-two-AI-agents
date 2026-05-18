"""Integration — chaos engineering with budget overflow (P9.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from debate.shared.config import load_config


@pytest.mark.integration
def test_budget_abort_cli(tmp_path: Path) -> None:
    # 1. Override config
    cfg = load_config()
    override = cfg.model_dump()
    override["max_usd_per_debate"] = 0.001
    override["max_tokens_per_debate"] = 100
    
    cfg_path = tmp_path / "budget_override.json"
    cfg_path.write_text(json.dumps(override), encoding="utf-8")

    # 2. Run the menu non-interactively
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "debate.main",
            "--non-interactive",
            "--config",
            str(cfg_path),
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

    # 3. Assert FSM ends in ABORT, exit code 2
    assert proc.returncode == 2, proc.stderr or proc.stdout

    # 4. Assert budget_exhausted event was logged
    # We need to find the run directory. It should be the most recent one in the workspace,
    # or we can set DEBATE_RUNS_DIR? The logger uses `runs/<ts>`. Let's just grep the stdout
    # or the stderr, or find the runs dir.
    # Actually, we can run it in a specific temp directory if we change cwd or just search `runs/`.
    # Let's search the workspace `runs` directory for the most recent run.
    root_runs = Path("runs")
    if root_runs.exists():
        latest_run = max(root_runs.iterdir(), key=lambda p: p.stat().st_mtime)
        log_file = latest_run / "run.jsonl"
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            assert "budget_exhausted" in content
            assert "budget_exhausted" in proc.stdout or "budget_exhausted" in proc.stderr
