# Handoff — HW2 AI Agent Debate (for new chat / context reset)

**Purpose of this file:** Give a future coding agent enough grounded detail to continue work without re-discovering repo basics, tooling traps, and known behavior quirks. Read this first, then `AGENTS.md`, then narrow files as needed.

**Authoritative project rules:** `AGENTS.md` (repo root) — always run from repo root; use `python -m uv` (not bare `uv` on Windows); verify with `python scripts/dev.py check`. Do **not** add new top-level directories; layout contract is `docs/PLAN_HW2.md` §2.

---

## 1. What this project is

- **Multi-process debate:** Parent **Judge** orchestrates two **child** debaters (Pro / Con) over a user motion, with bounded rounds, JSON line IPC (`\n`-framed), optional web search via judge-proxied tools, token/USD budgets (**Gatekeeper**), optional **Watchdog** heartbeats, structured logging under `runs/` (gitignored).
- **Entry:** `src/debate/main.py` — Rich terminal **menu** or CLI flags (`--non-interactive`, `--motion`, `--stub`, etc.).
- **Package name:** `debate`; code lives under `src/debate/` (install with `uv sync` / editable install so `python -m debate.main` resolves).

---

## 2. Clone → run (especially Windows)

1. `cd` to repo root (directory containing `pyproject.toml`).
2. Install uv once if needed: `python -m pip install uv`
3. `python -m uv sync --all-extras`
4. Run app: `python scripts/dev.py run` **or** `python -m uv run python -m debate.main`

**Common failures:**

- **`No module named 'debate'`** — You used a global `python` that never installed the project. Fix: use `python -m uv run …` from repo root, **or** activate `.venv` then `python -m debate.main`.
- **`No module named 'uv'`** (inside activated venv) — `uv` is not installed **in** that venv. Fix: `python -m pip install uv` with that venv’s python, **or** deactivate and use base Python that has uv, **or** always invoke via a Python that has the `uv` package.

**API keys:** Required for real runs (`LLM_API_KEY` in `.env`). Stub mode is **opt-in** only (`--stub` on the CLI or `force_stub=True` in tests); `src/debate/runner.py` calls `get_key("LLM_API_KEY")` when stub is not forced.

---

## 3. Directory map (high signal)

| Path | Role |
|------|------|
| `config/debate.json` | Rounds, models, token/USD caps, timeouts, `max_tokens_for_verdict`, etc. |
| `config/prompts/*.txt` | System prompts (judge, debater); `verdict.schema.json` |
| `src/debate/main.py` | CLI + menu |
| `src/debate/runner.py` | `run_debate()` — `Live(get_renderable=…)` so the panel re-reads live `Ctx` every refresh; stub vs real, timers |
| `src/debate/agents/judge_agent.py` | Orchestrator dataclass; `_pulse()` sets `_ui_last_speaker` and `Live.refresh()` |
| `src/debate/agents/judge_agent_runner.py` | `run_debate_impl` — lifecycle, watchdog stop |
| `src/debate/agents/judge_runner_fsm.py` | FSM `step()` — pro/con turns, scoring hooks, verdict, tie-break |
| `src/debate/agents/judge_ops_child.py` | `child_turn`, `closing_round`; logs `[OPS]` |
| `src/debate/agents/judge_rounds.py` | `score_reply`, `summarise_round`; logs `[ROUNDS]` |
| `src/debate/agents/judge_child*.py` | IPC to children (split across envelope/handlers modules) |
| `src/debate/orchestration/state_machine.py` | Pure FSM; `Ctx.round` starts at **1**; round increments in `_advance_round` after **Con** scored for the round |
| `src/debate/shared/gatekeeper.py` | Budget / execute wrapper |
| `src/debate/shared/budget.py` | `BudgetExceeded`, caps checks (tokens + USD) |
| `src/debate/ui/menu.py` | Menu; **Edit tunables** — field names are words: `rounds`, `model`, `budget`/`budget_usd`, `tokens`/`max_tokens` (not numbers); session-only unless persisted elsewhere |
| `src/debate/ui/status.py` | `DebateStatus`, `status_from_agent`, `render_panel` — `started_at` comes from `JudgeAgent._ui_started_at` (set in `runner.py`); stub runs show an **LLM** row |
| `tests/integration/test_behavioral_*.py` | Behavioral/regression tests; `behavioral_edge_wiring.py` helpers |
| `docs/PRD_HW2.md`, `docs/PLAN_HW2.md`, `docs/TODO_HW2.md` | Requirements, architecture, task checklist |

**Refactor note (historical):** Large agents were split into mixins/helpers (`base_agent_recv.py`, `base_agent_run.py`, `judge_tie_break_support.py`, `stub_llm_basic.py`, etc.). Public import surfaces were kept where possible; `judge_agent_ops.py` is largely re-exports.

---

## 4. Runtime / UX quirks (operator confusion — may deserve fixes)

These were observed in real terminal runs (Windows, Rich `Live` + stderr logging):

1. **`[OPS]` / `[ROUNDS]` / `[RUNNER]`** — During Rich `Live`, these lines are appended to `runs/<id>/judge.diag.log` instead of stderr so the stdout live panel is not corrupted. After the debate, stderr prints the log path. Other stderr (e.g. `[BUILD]`) may still appear before the live session starts.

2. **`Speaker` often shows `PRO` when `[OPS] con_reply` just appeared** — By design order in `judge_runner_fsm.py`: `child_turn` logs reply → **`score_reply`** (judge work, no `_pulse`) → **`_pulse("con")`**. So during Con’s scoring phase, panel can still show last speaker **PRO**. Misleading but consistent with current code.

3. **`budget_exhausted` + `ABORT` right after the last scored round (often at verdict)** — Default `max_requests_per_minute` used to be **30** while the judge process performs **three** gatekeeper LLM calls per content round (score Pro, score Con, summarise) plus **one** for the verdict → **3 × rounds + 1** requests (e.g. **31** for `rounds: 10`), so RPM tripped with a **small token/USD ledger** (RPM is separate from token totals). Defaults were raised and per-call output caps aligned with `max_tokens_for_verdict`; if you still hit RPM, raise `max_requests_per_minute` in `config/debate.json`. **`aborted_verdict`** returns placeholder winner **con** and canned reasons — not a judged outcome.

4. **Menu tunables:** Prompt says `Field (rounds/model/budget/tokens)` — entering `3` yields `unknown field`; must type the **word** `budget` etc.

5. **Tie-break display scores** (`judge_tie_break_support.verdict_scores_for_winner`) may **bump** verdict scores so winner strictly leads raw cumulative totals on numeric ties — intentional for schema alignment; reasons still cite cumulative story in text.

6. **Debater replies:** `ipc_safe_reply_text` in `debater_compose_format.py` collapses newlines for single-line JSON IPC.

---

## 5. Verification

```bash
python -m uv sync --all-extras
python scripts/dev.py check
```

Runs: ruff check → ruff format --check → secret scan → pytest.

---

## 6. Suggested reading order for a new task

1. This file  
2. `AGENTS.md`  
3. `docs/PLAN_HW2.md` §2 (layout) + relevant phase section  
4. Touch only the files your task needs (FSM: `state_machine.py` + `judge_runner_fsm.py`; UI: `status.py` + `runner.py` + `judge_agent.py`; budget: `budget.py` + `gatekeeper.py`)

---

## 7. Continuation prompt snippet (optional paste for user)

> Read `docs/HANDOFF_FOR_AGENTS.md` and `AGENTS.md`, then continue from repo root. Obey PLAN §2 layout; run `python scripts/dev.py check` before finishing.

---

*Last updated: handoff written from multi-session analysis (run paths, UI/budget quirks, tooling). Update this file when architecture or operator workflows materially change.*
