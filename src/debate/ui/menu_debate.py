"""Menu-driven debate start: motions file, stub prompt when no API key, outcome."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from debate.runner import run_debate
from debate.sdk.payloads import VerdictPayload
from debate.shared.config import Config
from debate.shared.secrets import MissingSecretError, get_env

DEFAULT_MOTION = "Artificial intelligence will do more good than harm for humanity."


def load_motions(root: Path) -> list[str]:
    path = root / "config" / "motions.json"
    if not path.is_file():
        return [DEFAULT_MOTION]
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("motions", [DEFAULT_MOTION]))


def _print_result(console: Console, verdict: VerdictPayload, run_dir: str, code: int) -> None:
    console.print(f"\n[bold green]Winner:[/] {verdict.winner.upper()}")
    console.print(f"Scores: pro={verdict.scores.pro} con={verdict.scores.con}")
    for r in verdict.reasons[:3]:
        console.print(f"  • {r[:90]}")
    console.print(f"Transcript: {run_dir}  (exit {code})")


def start_menu_debate(console: Console, cfg: Config, motion: str) -> None:
    console.print(f"\n[cyan]Starting debate[/]: {motion[:70]}…")
    force_stub = False
    if not (get_env("LLM_API_KEY") or "").strip():
        try:
            ans = (
                Prompt.ask(
                    "No LLM_API_KEY found. Run this session with the [bold]offline stub[/] "
                    "LLM? (y/N)",
                    default="n",
                    console=console,
                )
                .strip()
                .lower()
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")
            return
        if ans not in ("y", "yes"):
            console.print(
                "[yellow]Add LLM_API_KEY to .env (copy from .env-example), "
                "or answer y to use the stub.[/]"
            )
            return
        force_stub = True
    try:
        outcome = run_debate(cfg, motion, live=True, force_stub=force_stub)
    except MissingSecretError:
        console.print(
            "\n[red]FATAL:[/] LLM_API_KEY is missing or empty.\n"
            "Copy [bold].env-example[/] to [bold].env[/] in the repo root "
            "and set LLM_API_KEY.\n"
            "CLI: use [bold]--stub[/] for a non-interactive stub run."
        )
        return
    _print_result(console, outcome.verdict, outcome.run_dir, outcome.exit_code)
