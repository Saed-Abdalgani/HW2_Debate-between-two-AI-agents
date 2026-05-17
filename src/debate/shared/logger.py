"""Structured JSONL logger with secret redaction and per-run artefact paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from debate.shared.secrets import get_env, redact

_ROOT = Path(__file__).resolve().parents[3]
_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class LoggerError(Exception):
    pass


def project_root() -> Path:
    return _ROOT


def ensure_run_dir(project_root: Path, run_dir: Path) -> Path:
    """Reject paths outside <project>/runs/ (path-traversal guard)."""
    runs_root = (project_root.resolve() / "runs").resolve()
    resolved = run_dir.resolve()
    if resolved != runs_root and runs_root not in resolved.parents:
        raise LoggerError(f"run directory must be under {runs_root}")
    return resolved


class Logger:
    """Append-only JSONL transcript writer; flushes after every line."""

    def __init__(self, run_dir: Path, *, root: Path | None = None, log_level: str | None = None):
        base = root or _ROOT
        self.run_dir = ensure_run_dir(base, run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.run_dir / "run.jsonl"
        self._level = (log_level or get_env("LOG_LEVEL", "INFO") or "INFO").upper()
        self._file = self.jsonl_path.open("a", encoding="utf-8")
        self._console = Console(stderr=True)

    @classmethod
    def open_run(cls, *, root: Path | None = None, log_level: str | None = None) -> Logger:
        base = root or _ROOT
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return cls(base / "runs" / stamp, root=base, log_level=log_level)

    def stderr_path(self, role: str) -> Path:
        return self.run_dir / f"{role}.stderr.log"

    def event(
        self,
        event_type: str,
        *,
        role: str = "judge",
        turn_id: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        usd_cost: float = 0.0,
        **data: Any,
    ) -> None:
        record = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "role": role,
            "turn_id": turn_id,
            "event_type": event_type,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd_cost": usd_cost,
            "data": data,
        }
        safe = redact(record)
        self._file.write(json.dumps(safe, ensure_ascii=False) + "\n")
        self._file.flush()
        self._mirror(event_type, safe)

    def _mirror(self, event_type: str, record: dict[str, Any]) -> None:
        if _LOG_LEVELS.get(self._level, 20) > _LOG_LEVELS["INFO"]:
            return
        self._console.print(f"[cyan]{event_type}[/] role={record['role']} turn={record['turn_id']}")

    def close(self) -> None:
        self._file.close()
