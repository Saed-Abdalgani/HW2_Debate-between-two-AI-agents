# HW2 — AI Agent Debate

Multi-process debate system: a Parent Judge orchestrates Pro and Con debater agents
over line-delimited JSON IPC, with token budgeting (Gatekeeper) and process recovery
(Watchdog).

## Quick start (humans and AI agents)

**AI agents:** read [`AGENTS.md`](AGENTS.md) first — it defines what to run for
"run the code", "check", and "full workflow".

### Run the application

```bash
python -m uv sync --all-extras
python -m uv run python -m debate.main
```

Or: `python scripts/dev.py run` (after `python scripts/dev.py setup` on a fresh clone).

Expected output today: `HW2 Debate scaffold OK`

### Verify (lint, format, secret scan, tests)

```bash
python scripts/dev.py check
```

### Setup + verify + run (one command)

```bash
python scripts/dev.py all
```

Use `python -m uv` instead of `uv` if `uv` is not on your PATH.

## Documentation

- [`AGENTS.md`](AGENTS.md) — command cheat sheet for coding agents
- [`docs/PRD_HW2.md`](docs/PRD_HW2.md) — requirements
- [`docs/PLAN_HW2.md`](docs/PLAN_HW2.md) — architecture and IPC schema
- [`docs/TODO_HW2.md`](docs/TODO_HW2.md) — phased implementation roadmap
