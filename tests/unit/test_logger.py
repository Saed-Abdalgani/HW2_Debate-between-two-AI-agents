"""Unit tests for structured JSONL logger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from debate.shared.logger import Logger, LoggerError, ensure_run_dir


@pytest.mark.unit
def test_event_writes_valid_jsonl(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "20260101T000000000000Z"
    logger = Logger(run_dir, root=tmp_path)
    logger.event("turn_complete", role="pro", turn_id=2, tokens_in=10, tokens_out=20)
    logger.close()
    lines = logger.jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["event_type"] == "turn_complete"
    assert record["turn_id"] == 2
    assert record["tokens_in"] == 10


@pytest.mark.unit
def test_secrets_never_in_jsonl(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "secret_run"
    logger = Logger(run_dir, root=tmp_path)
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    logger.event("llm_call", data={"auth": f"Bearer {secret}"})
    logger.close()
    raw = logger.jsonl_path.read_bytes()
    assert secret.encode() not in raw
    assert b"***REDACTED***" in raw


@pytest.mark.unit
def test_path_traversal_blocked(tmp_path: Path) -> None:
    outside = tmp_path / "evil"
    with pytest.raises(LoggerError):
        ensure_run_dir(tmp_path, outside)


@pytest.mark.unit
def test_stderr_path_layout(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "layout"
    logger = Logger(run_dir, root=tmp_path)
    assert logger.stderr_path("pro") == run_dir / "pro.stderr.log"


@pytest.mark.unit
def test_open_run_under_project_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("debate.shared.logger._ROOT", tmp_path)
    logger = Logger.open_run(root=tmp_path)
    try:
        assert logger.run_dir.parent.name == "runs"
        assert logger.run_dir.is_dir()
    finally:
        logger.close()


@pytest.mark.unit
def test_flush_after_each_line(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "flush"
    logger = Logger(run_dir, root=tmp_path)
    logger.event("ping")
    assert logger.jsonl_path.stat().st_size > 0
    logger.close()
