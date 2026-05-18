"""Read-only replay of saved runs (no network, no children)."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console


def list_run_dirs(runs_root: Path) -> list[Path]:
    if not runs_root.is_dir():
        return []
    return sorted(
        (p for p in runs_root.iterdir() if p.is_dir() and (p / "run.jsonl").is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def replay_run(run_dir: Path, console: Console | None = None) -> None:
    path = run_dir / "run.jsonl"
    out = console or Console()
    out.print(f"[bold]Replay[/] {run_dir.name}\n")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        etype = record.get("event_type", "?")
        role = record.get("role", "?")
        turn = record.get("turn_id", 0)
        data = record.get("data", {})
        if etype == "verdict":
            out.print(f"[yellow]VERDICT[/] winner={data.get('winner')} scores={data.get('scores')}")
            for reason in data.get("reasons", [])[:5]:
                out.print(f"  - {reason[:100]}")
        elif etype == "score":
            out.print(f"[dim]score[/] {role} turn {turn}: {data.get('score')}")
        else:
            out.print(f"[dim]{etype}[/] role={role} turn={turn}")
