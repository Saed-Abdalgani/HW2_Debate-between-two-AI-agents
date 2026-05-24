"""Entry point — menu or non-interactive debate (P8.3)."""

from __future__ import annotations

import argparse
import contextlib
import signal
import sys
from pathlib import Path

from debate.runner import run_debate
from debate.shared.config import load_config
from debate.shared.secrets import MissingSecretError
from debate.ui.menu import run_menu

_AGENT: object | None = None


def _shutdown_children(*_args: object) -> None:
    agent = _AGENT
    if agent is not None and hasattr(agent, "supervisor"):
        agent.supervisor.shutdown_all()  # type: ignore[union-attr]
    raise SystemExit(130)


def _install_signals() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(ValueError, OSError):
            signal.signal(sig, _shutdown_children)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW2 AI Agent Debate")
    parser.add_argument("--config", type=Path, default=None, help="Path to debate.json")
    parser.add_argument("--motion", type=str, default=None, help="Debate motion (CI mode)")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run one debate and exit (no menu); requires LLM_API_KEY unless --stub",
    )
    parser.add_argument("--rounds", type=int, default=None, help="Override round count")
    parser.add_argument("--stub", action="store_true", help="Force stub LLM for judge and children")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        _main_body(args)
    except MissingSecretError as exc:
        sys.stderr.write(
            "\nFATAL: "
            + str(exc)
            + "\nCopy .env-example to .env in the repo root and set a non-empty LLM_API_KEY.\n"
            "For offline or CI runs without a provider key, pass --stub explicitly.\n"
        )
        raise SystemExit(2) from exc


def _main_body(args: argparse.Namespace) -> None:
    if args.config:
        import os

        os.environ["DEBATE_CONFIG"] = str(args.config)
    cfg = load_config()
    if args.rounds is not None:
        cfg.rounds = max(1, args.rounds)

    _install_signals()

    if args.non_interactive:
        motion = args.motion or "Remote work should remain the default for knowledge workers."
        outcome = run_debate(cfg, motion, live=False, force_stub=args.stub)
        print(f"Winner: {outcome.verdict.winner}  run={outcome.run_dir}")
        raise SystemExit(outcome.exit_code)

    if args.motion:
        outcome = run_debate(cfg, args.motion, live=True, force_stub=args.stub)
        raise SystemExit(outcome.exit_code)

    run_menu(cfg)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        sys.exit(exc.code if exc.code is not None else 0)
    except KeyboardInterrupt:
        sys.exit(130)
