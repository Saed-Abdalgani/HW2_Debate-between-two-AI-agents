"""Terminal menu — rich UI (P8.1)."""

from __future__ import annotations

import json

from rich.console import Console
from rich.prompt import Prompt

from debate.runner import run_debate
from debate.shared.config import Config, load_config
from debate.shared.logger import project_root
from debate.ui.replay import list_run_dirs, replay_run
from debate.ui.tunables import apply_budget_usd, apply_max_tokens, apply_model, apply_rounds

_DEFAULT_MOTION = "Artificial intelligence will do more good than harm for humanity."


class Menu:
    """Numbered operator menu; keeps an in-memory ``Config`` copy."""

    def __init__(self, cfg: Config, *, console: Console | None = None) -> None:
        self.cfg = cfg
        self.console = console or Console()
        self._root = project_root()
        self._motions = self._load_motions()

    def _load_motions(self) -> list[str]:
        path = self._root / "config" / "motions.json"
        if not path.is_file():
            return [_DEFAULT_MOTION]
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("motions", [_DEFAULT_MOTION]))

    def run_loop(self) -> None:
        while True:
            self.console.print("\n[bold]HW2 AI Debate[/]")
            self.console.print(
                "1) Start (default motion)  2) Pick motion  3) Custom motion\n"
                "4) Edit tunables  5) Replay run  6) Quit"
            )
            try:
                choice = Prompt.ask("Choice", default="6", console=self.console).strip()
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Back to menu.[/]")
                continue
            if choice == "1":
                self._start(self._motions[0] if self._motions else _DEFAULT_MOTION)
            elif choice == "2":
                self._pick_motion()
            elif choice == "3":
                self._custom_motion()
            elif choice == "4":
                self._edit_tunables()
            elif choice == "5":
                self._replay()
            elif choice == "6":
                break
            else:
                self.console.print("[red]Invalid choice.[/]")

    def _start(self, motion: str) -> None:
        self.console.print(f"\n[cyan]Starting debate[/]: {motion[:70]}…")
        outcome = run_debate(self.cfg, motion, live=True)
        self._print_result(outcome.verdict, outcome.run_dir, outcome.exit_code)

    def _pick_motion(self) -> None:
        for i, m in enumerate(self._motions, start=1):
            self.console.print(f"  {i}) {m[:72]}")
        try:
            raw = Prompt.ask("Motion #", console=self.console).strip()
            idx = int(raw) - 1
        except (KeyboardInterrupt, ValueError):
            self.console.print("[red]Invalid selection.[/]")
            return
        if idx < 0 or idx >= len(self._motions):
            self.console.print("[red]Out of range.[/]")
            return
        self._start(self._motions[idx])

    def _custom_motion(self) -> None:
        try:
            motion = Prompt.ask("Motion text", console=self.console).strip()
        except KeyboardInterrupt:
            return
        if len(motion) < 10:
            self.console.print("[red]Motion too short (min 10 chars).[/]")
            return
        self._start(motion)

    def _edit_tunables(self) -> None:
        self.console.print(
            f"rounds={self.cfg.rounds} model={self.cfg.model} "
            f"budget=${self.cfg.max_usd_per_debate} max_tokens={self.cfg.max_tokens_per_turn}"
        )
        field = Prompt.ask("Field (rounds/model/budget/tokens)", console=self.console).strip()
        try:
            value = Prompt.ask("New value", console=self.console).strip()
        except KeyboardInterrupt:
            return
        err = self._apply_field(field, value)
        if err:
            self.console.print(f"[red]{err}[/]")
        else:
            self.console.print("[green]Updated (session only).[/]")

    def _apply_field(self, field: str, value: str) -> str | None:
        key = field.lower()
        if key == "rounds":
            return apply_rounds(self.cfg, value)
        if key == "model":
            return apply_model(self.cfg, value)
        if key in {"budget", "budget_usd"}:
            return apply_budget_usd(self.cfg, value)
        if key in {"tokens", "max_tokens"}:
            return apply_max_tokens(self.cfg, value)
        return f"unknown field: {field}"

    def _replay(self) -> None:
        runs = list_run_dirs(self._root / "runs")
        if not runs:
            self.console.print("[yellow]No saved runs.[/]")
            return
        for i, path in enumerate(runs[:10], start=1):
            self.console.print(f"  {i}) {path.name}")
        try:
            raw = Prompt.ask("Run #", console=self.console).strip()
            replay_run(runs[int(raw) - 1], self.console)
        except (KeyboardInterrupt, ValueError, IndexError):
            self.console.print("[red]Invalid selection.[/]")

    def _print_result(self, verdict, run_dir: str, code: int) -> None:
        self.console.print(f"\n[bold green]Winner:[/] {verdict.winner.upper()}")
        self.console.print(f"Scores: pro={verdict.scores.pro} con={verdict.scores.con}")
        for r in verdict.reasons[:3]:
            self.console.print(f"  • {r[:90]}")
        self.console.print(f"Transcript: {run_dir}  (exit {code})")


def run_menu(cfg: Config | None = None) -> None:
    Menu(cfg or load_config()).run_loop()
