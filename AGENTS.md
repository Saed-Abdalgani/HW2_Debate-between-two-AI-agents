# Agent instructions — HW2 AI Agent Debate

This file tells coding agents **exactly** which commands to run. Follow it when the
user says things like "run the code", "run the project", "start the app", or
"verify the project".

**Always run commands from the repository root** (the folder that contains
`pyproject.toml`).

**Always use `python -m uv`** (not bare `uv`) so commands work when `uv` is not on
`PATH` (common on Windows).

---

## Run the application

When the user wants to **run** or **execute** the project:

```bash
python -m uv sync --all-extras
python -m uv run python -m debate.main
```

Expected stdout (current scaffold phase): `HW2 Debate scaffold OK`

Equivalent one-liner:

```bash
python scripts/dev.py run
```

(`dev.py run` runs `uv sync` implicitly via `uv run`; run `setup` first on a fresh
clone — see below.)

---

## Verify the project (lint, format, secrets, tests)

When the user wants to **test**, **check**, **validate**, or **make sure everything
passes**:

```bash
python -m uv sync --all-extras
python scripts/dev.py check
```

`check` runs, in order: `ruff check` → `ruff format --check` → secret scan →
`pytest -q`.

---

## Full workflow (setup + verify + run)

When the user wants everything — install deps, verify, then run:

```bash
python scripts/dev.py all
```

This runs `setup` → `check` → `run` (same commands as the two sections above).

---

## Command reference

| User intent              | Command                          |
|--------------------------|----------------------------------|
| Run the app              | `python scripts/dev.py run`      |
| Run tests / CI check     | `python scripts/dev.py check`    |
| Install dependencies     | `python scripts/dev.py setup`    |
| Setup + check + run      | `python scripts/dev.py all`      |
| Lint only                | `python scripts/dev.py lint`     |
| Tests only               | `python scripts/dev.py test`     |

---

## Prerequisites

- Python 3.12+ (project uses 3.14 in local `.python-version` if present)
- `uv` installable via `python -m pip install uv` if missing
- API keys are **not** required for the current scaffold (`debate.main` prints a
  banner only). Later phases need `.env` copied from `.env-example`.

---

## Architecture docs

- Requirements: `docs/PRD_HW2.md`
- Implementation plan: `docs/PLAN_HW2.md`
- Task roadmap: `docs/TODO_HW2.md`

Do not invent new top-level directories; follow `docs/PLAN_HW2.md` §2.
