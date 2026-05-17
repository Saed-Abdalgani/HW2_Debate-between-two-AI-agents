"""Development helper: lint, test, run, and secret scan."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"LLM_API_KEY=sk-[A-Za-z0-9]{10,}"),
    re.compile(r"SEARCH_API_KEY=[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd, cwd=ROOT)


def scan_secrets() -> int:
    """Fail if the working tree contains obvious secret literals."""
    hits: list[str] = []
    skip = {".git", ".venv", "runs", "tests", "__pycache__", ".pytest_cache", ".ruff_cache", "docs"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.suffix in {".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path}: matched {pattern.pattern}")
    if hits:
        for line in hits:
            print(line, file=sys.stderr)
        return 1
    return 0


def _setup() -> int:
    return _run([sys.executable, "-m", "uv", "sync", "--all-extras"])


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "usage: dev.py {setup|lint|format|test|run|check|scan|all}",
            file=sys.stderr,
        )
        sys.exit(2)
    cmd = sys.argv[1]
    uv = [sys.executable, "-m", "uv"]
    steps: dict[str, list[str] | None] = {
        "setup": None,
        "lint": [*uv, "run", "ruff", "check"],
        "format": [*uv, "run", "ruff", "format", "--check"],
        "test": [*uv, "run", "pytest", "-q"],
        "run": [*uv, "run", "python", "-m", "debate.main"],
        "scan": None,
    }
    if cmd == "setup":
        sys.exit(_setup())
    if cmd == "check":
        if _setup():
            sys.exit(1)
        for step in ("lint", "format", "scan", "test"):
            code = scan_secrets() if step == "scan" else _run(steps[step])  # type: ignore[arg-type]
            if code:
                sys.exit(code)
        sys.exit(0)
    if cmd == "all":
        if _setup():
            sys.exit(1)
        for step in ("lint", "format", "scan", "test", "run"):
            if step == "scan":
                code = scan_secrets()
            elif step == "run":
                code = _run(steps["run"])  # type: ignore[arg-type]
            else:
                code = _run(steps[step])  # type: ignore[arg-type]
            if code:
                sys.exit(code)
        sys.exit(0)
    if cmd == "scan":
        sys.exit(scan_secrets())
    if cmd not in steps:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
    if cmd in {"lint", "format", "test", "run"} and _setup():
        sys.exit(1)
    sys.exit(_run(steps[cmd]))  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
