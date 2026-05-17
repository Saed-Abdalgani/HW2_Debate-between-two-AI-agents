# Product Requirements Document — HW2 AI Agent Debate

| Field    | Value               |
|----------|---------------------|
| Document | PRD_HW2.md          |
| Version  | 1.00                |
| Status   | Draft — Bootstrap   |
| Updated  | 2026-05-17          |
| Owner    | Senior Architect    |

---

## 1. Executive Summary

HW2 delivers a **multi-process agentic system** in which a **Parent Judge** agent
orchestrates two **Child Debater** agents (Pro and Con) through a structured,
bounded debate on a user-supplied motion. Each debater may consult an internet
search tool to gather evidence; all inter-process communication is line-delimited
JSON; the Judge must render a **non-tie verdict** and produce a structured,
auditable transcript. The system is governed by a **Gatekeeper** (token / budget /
key custody) and a **Watchdog** (process health and recovery), and is operated
through a **terminal menu** with all parameters sourced from JSON config and
environment variables — no hardcoded values.

This PRD is the contract; `docs/PLAN_HW2.md` is the implementation plan.

---

## 2. Goals and Non-Goals

### 2.1 Goals
- G1. Run a deterministic, bounded debate (exactly **10 pings** per side).
- G2. Provide each debater with internet search access via a controlled tool.
- G3. Produce a persuasive, justified **non-tie** verdict from the Judge.
- G4. Enforce a hard **token / cost budget** through the Gatekeeper.
- G5. Survive a single child crash via automatic Watchdog recovery.
- G6. Emit a fully **structured log** of every prompt, response, tool call, and
  verdict suitable for offline grading and reproducibility.

### 2.2 Non-Goals
- NG1. No GUI / web UI — terminal menu only.
- NG2. No fine-tuning or local model hosting — provider API calls only.
- NG3. No human-in-the-loop scoring; the Judge is the sole adjudicator.
- NG4. No multi-debate parallelism in v1 (one debate at a time).

---

## 3. Personas and User Stories

- **Operator (course user / grader).** Launches the program, picks a motion,
  observes the debate streaming in the terminal, reads the verdict, inspects
  the saved transcript and budget report.
- **Judge Agent (Parent).** Defines the motion, enforces the protocol, scores
  arguments, summarises context, issues the verdict.
- **Debater Agent (Child Pro / Con).** Defends an assigned stance, searches the
  web when useful, replies within token caps, never breaks the JSON contract.

User stories:
- US-1. *As an Operator,* I can pick a motion from a config-driven list or type
  my own, so I can grade the system on arbitrary topics.
- US-2. *As an Operator,* I can set a hard token budget and have the run abort
  cleanly when it is exhausted.
- US-3. *As a Judge,* I receive each ping as a typed JSON message so I never
  have to parse free text.
- US-4. *As a Debater,* I can issue a `search` tool call and receive cached
  results without re-paying for duplicate queries.

---

## 4. System Overview

```
┌────────────────────────────── Parent Process ──────────────────────────────┐
│                              Judge Agent                                   │
│   ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────────┐  │
│   │  Menu    │──▶│ State Machine│──▶│ Gatekeeper│──▶│ LLMClient (SDK)  │  │
│   └──────────┘   └──────┬───────┘   └─────┬─────┘   └──────────────────┘  │
│                         │                 │                                │
│                  ┌──────┴──────┐    ┌─────┴──────┐                         │
│                  │  Watchdog   │    │  Logger    │                         │
│                  └──────┬──────┘    └────────────┘                         │
└─────────────────────────┼──────────────────────────────────────────────────┘
                          │ stdin/stdout JSON pipes
                ┌─────────┴──────────┐
                ▼                    ▼
        ┌──────────────┐      ┌──────────────┐
        │  Pro Agent   │      │  Con Agent   │
        │ (subprocess) │      │ (subprocess) │
        │  + Search    │      │  + Search    │
        └──────────────┘      └──────────────┘
```

The Judge is the only process with file-system / network privileges beyond LLM +
search; children inherit a restricted environment.

---

## 5. Functional Requirements

| ID    | Requirement                                                                                              | Priority |
|-------|----------------------------------------------------------------------------------------------------------|----------|
| FR-1  | Operator selects a motion via terminal menu; motions list lives in `config/motions.json`.                | MUST     |
| FR-2  | Judge spawns exactly two children: one Pro, one Con, each as an isolated OS process.                     | MUST     |
| FR-3  | Debate runs for exactly **10 pings per side** (configurable as `rounds`, default 10).                    | MUST     |
| FR-4  | All IPC messages are **single-line UTF-8 JSON** terminated by `\n`, conforming to the schema in PLAN §6. | MUST     |
| FR-5  | Each debater MAY emit `tool_call: "search"` messages; Judge proxies them through the cached search tool. | MUST     |
| FR-6  | Search results are cached by SHA-256 of the normalised query for the lifetime of the debate.             | MUST     |
| FR-7  | Each ping carries a monotonically increasing `turn_id` and a parent-side timestamp.                      | MUST     |
| FR-8  | Judge MUST return a verdict object with `winner ∈ {"pro","con"}` — **`"tie"` is rejected**.              | MUST     |
| FR-9  | If the Judge's first verdict is malformed or returns a tie, it is re-prompted **once**; on second        | MUST     |
|       | failure a deterministic tie-breaker (higher cumulative argument score) selects the winner.               |          |
| FR-10 | The full transcript (every JSON message + verdict + budget report) is written to `runs/<ts>/run.jsonl`.  | MUST     |
| FR-11 | Operator can re-play a saved run from disk in read-only mode.                                            | SHOULD   |
| FR-12 | Operator can set `rounds`, `model`, `budget_usd`, `max_tokens_per_turn` from the menu before launch.     | SHOULD   |


---

## 6. Non-Functional Requirements

### 6.1 Token Economics — Gatekeeper
- NFR-1. A **Gatekeeper** module wraps every outbound LLM and search call.
- NFR-2. Hard caps enforced **before** dispatch:
  `max_tokens_per_turn`, `max_tokens_per_debate`, `max_usd_per_debate`,
  `max_requests_per_minute`. Values come from `config/debate.json` / `.env`.
- NFR-3. The Gatekeeper maintains a running ledger (`tokens_in`, `tokens_out`,
  `usd_spent`, `requests`) and refuses calls that would exceed any cap; the
  Judge then performs a graceful shutdown and emits a `budget_exhausted` event.
- NFR-4. **Context Engineering — Select / Write.** The Gatekeeper exposes a
  `select_context(role, turn_id)` helper that returns only the slice each
  agent needs (own last reply, opponent's last reply, rolling summary) and a
  `write_summary(role, turn_id, text)` helper that persists the rolling
  summary to disk. Agents never see the full transcript directly.
- NFR-5. **Router-Skill caching.** A `SkillRouter` dispatches tool calls to
  named skills (`search`, `summarise`, `score`). The `search` skill is
  content-hash cached; repeated identical queries within a debate are served
  from cache at zero token cost.

### 6.2 Process Reliability — Watchdog
- NFR-6. A **Watchdog** runs in a dedicated thread inside the Judge process.
- NFR-7. Every `heartbeat_sec` (default 5 s) it sends a `{"type":"ping"}` to
  each child; children must reply with `{"type":"pong","turn_id":...}` within
  `heartbeat_timeout_sec` (default 3 s).
- NFR-8. On missed heartbeat: `SIGTERM → wait grace → SIGKILL → respawn`. The
  Judge replays the last *outbound* prompt to the new child. Maximum
  `max_restarts_per_child` (default 2); exceeded → debate aborts cleanly with
  a `child_unrecoverable` event written to the transcript.
- NFR-9. All child stderr is captured to `runs/<ts>/<role>.stderr.log`.

### 6.3 Cybersecurity — Key & Secret Management
- NFR-10. All API keys live exclusively in environment variables loaded from
  `.env` (gitignored). `.env-example` documents the variable names with empty
  values. Keys MUST NOT appear in source, logs, transcripts, or CLI output.
- NFR-11. The Gatekeeper redacts known secret patterns from any logged payload
  before write (regex allow-list applied to every JSON record).
- NFR-12. Child processes receive only the keys they need; the search key is
  passed only to the Judge, never inherited by debaters (the Judge proxies).
- NFR-13. JSON payloads received from children are size-limited
  (`max_message_bytes`, default 64 KiB) and schema-validated before any
  downstream use — defence against prompt-injection inflation.

### 6.4 Performance & Observability
- NFR-14. End-to-end debate wall time SHOULD be ≤ 10 min on a single laptop
  with default settings (network-bound).
- NFR-15. Every JSON line in `run.jsonl` carries `ts`, `role`, `turn_id`,
  `event_type`, `tokens_in`, `tokens_out`, and `usd_cost`.
- NFR-16. A terminal status panel refreshes after each turn with running
  totals (tokens, USD, elapsed, current speaker).

### 6.5 Maintainability
- NFR-17. Python source files ≤ 150 lines each (carried over from HW1).
- NFR-18. 100 % of tunables live in `config/*.json` or `.env`; a grep for
  numeric literals in `src/` returns only architectural constants
  (e.g., JSON schema version).
- NFR-19. Toolchain: **`uv`** (env + deps), **`ruff`** (lint + format),
  **`pytest`** (unit + integration). All three runnable from a single
  `make`-less script invoked by the menu.

---

## 7. Success Criteria

| ID   | Criterion                                                                                  | Verification                |
|------|--------------------------------------------------------------------------------------------|-----------------------------|
| SC-1 | A full 10-ping debate completes end-to-end on the default motion within budget.            | Integration test + manual   |
| SC-2 | The Judge produces a non-tie verdict with a justification ≥ 3 reasoned points.             | Schema test + sample review |
| SC-3 | Killing a child mid-debate (`kill -9`) triggers automatic recovery and the debate finishes.| Chaos test                  |
| SC-4 | Exceeding the configured token cap aborts the debate cleanly with a `budget_exhausted` log.| Unit + integration test     |
| SC-5 | No API key appears in `runs/`, stdout, or git history.                                     | Regex scan in CI            |
| SC-6 | `ruff check` and `pytest` both pass on a clean `uv sync`.                                  | CI / pre-commit             |
| SC-7 | Re-running with identical seed/motion/cached search produces an identical transcript hash up to stochastic LLM replies. | Replay test |

---

## 8. Configuration Surface (illustrative)

`config/debate.json`
```json
{
  "rounds": 10,
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens_per_turn": 800,
  "max_tokens_per_debate": 60000,
  "max_usd_per_debate": 1.50,
  "max_requests_per_minute": 30,
  "heartbeat_sec": 5,
  "heartbeat_timeout_sec": 3,
  "max_restarts_per_child": 2,
  "max_message_bytes": 65536,
  "search": { "provider": "tavily", "max_results": 5, "cache": true }
}
```

`.env-example`
```
LLM_API_KEY=
SEARCH_API_KEY=
LOG_LEVEL=INFO
```

---

## 9. Risks and Mitigations

| Risk                                  | Likelihood | Impact | Mitigation                                                  |
|---------------------------------------|------------|--------|-------------------------------------------------------------|
| LLM produces invalid JSON             | High       | Med    | Strict schema + 1 retry + tie-breaker rule (FR-9)           |
| Runaway token spend                   | Med        | High   | Gatekeeper hard caps (NFR-2)                                |
| Child process hangs                   | Med        | High   | Watchdog heartbeat + respawn (NFR-7,8)                      |
| Prompt injection from search results  | Med        | Med    | Size-limit + schema validation + result sanitiser (NFR-13)  |
| API key leakage in logs               | Low        | High   | Env-only secrets + log redactor (NFR-10,11)                 |
| Judge bias / tie-spamming             | Med        | Med    | Schema rejects "tie"; deterministic tie-breaker (FR-8,9)    |

---

## 10. Out of Scope (v1)

- Multi-motion campaigns or tournament brackets.
- Streaming token-level UI (only turn-level streaming).
- Local LLM hosting.
- Concurrent debates in the same Judge process.

---

## 11. Acceptance Test Outline

1. `uv sync && uv run ruff check && uv run pytest -q` → green.
2. `uv run python -m debate.main` → menu appears; select default motion.
3. Debate streams 10 pings per side, with running token counter in panel.
4. Verdict is non-tie, includes ≥ 3 reasons; transcript saved.
5. `kill -9 <pro pid>` mid-debate (chaos run) → Watchdog respawns Pro, debate
   resumes and completes.
6. Set `max_usd_per_debate: 0.001` → run aborts with `budget_exhausted` event.
7. `grep -R "$LLM_API_KEY" runs/` returns nothing.
