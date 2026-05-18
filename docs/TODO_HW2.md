# Master Execution Roadmap — HW2 AI Agent Debate

| Field    | Value                                  |
|----------|----------------------------------------|
| Document | TODO_HW2.md                            |
| Version  | 1.00                                   |
| Status   | P0–P8 complete; P9 pending              |
| Updated  | 2026-05-18                             |
| Pairs    | `docs/PRD_HW2.md`, `docs/PLAN_HW2.md`  |
| Owner    | Senior Architect                       |

---

## 0. How to Read This Document

This roadmap is the single source of truth for **what** must be built and **in
what order**. Every task carries:

- **Checkbox** (`[ ]` open / `[x]` done / `[~]` in-progress / `[!]` blocked).
- **Priority** — **M** (Must, blocks the phase), **S** (Should, blocks
  release), **C** (Could, nice-to-have).
- **Trace** — references back to `FR-x` / `NFR-x` / `SC-x` (PRD) or
  `§n` (PLAN) so reviewers can audit coverage.
- **DoD** — every phase ends with a "Definition of Done" checklist; a phase
  is not "complete" until **every** DoD line is green.

Five concerns are applied to **every** non-trivial component:

1. **Implementation** — the code itself, ≤ 150 lines per file (NFR-17).
2. **Defensive Programming** — schema validation, IPC error paths, signal
   handling, timeouts.
3. **Testing (TDD)** — unit tests for edge cases authored alongside code.
4. **Security & Compliance** — secret custody, log redaction, budget caps.
5. **Documentation** — docstrings + final README/lab-report update.

Conventions:

- Repo layout is **§2** of `PLAN_HW2.md`. Do not invent new directories.
- All numeric/tunable values come from `config/debate.json` or `.env`
  (NFR-18). PRs that introduce magic numbers are rejected.
- All Python files must pass `uv run ruff check` and `uv run ruff format
  --check`; all tests must pass `uv run pytest -q` (NFR-19).
- Commit messages: `[Pn] short description` (e.g., `[P3] Gatekeeper ledger
  + USD conversion`).

---

## Phase P0 — Repository Scaffold & Toolchain

**Goal.** Empty repo → working `uv` environment with `ruff` + `pytest`
green on a stub package.
**Exit Criterion (PLAN §8).** `uv sync` clean; `ruff check` green.

### P0.1 Project Scaffold

- [x] **M** Initialise repo: `uv init --package debate` at the workspace
  root. Trace: §2, NFR-19.
- [x] **M** Create directory tree exactly as per `PLAN_HW2.md` §2:
  `src/debate/{sdk,agents,orchestration,shared,ui}`, `tests/{unit,integration}`,
  `config/prompts`, `docs`, `runs` (gitignored).
- [x] **M** Add empty `__init__.py` in every package directory.
- [x] **M** Add a stub `src/debate/main.py` that prints
  `"HW2 Debate scaffold OK"` and exits 0 so `uv run python -m debate.main`
  works on day one.

### P0.2 Toolchain Configuration

- [x] **M** `uv add pydantic httpx python-dotenv jsonschema rich`
  (runtime). Trace: PLAN §7.1.
- [x] **M** `uv add --dev ruff pytest pytest-asyncio pytest-cov`.
- [x] **M** `pyproject.toml` → `[tool.ruff]` block: line-length 100,
  rule sets `E, F, I, UP, B, SIM, RUF`, double-quote style. Trace: PLAN §7.2.
- [x] **M** `pyproject.toml` → `[tool.pytest.ini_options]`: `testpaths =
  ["tests"]`, `addopts = "-ra -q --strict-markers"`, register markers
  `unit`, `integration`, `chaos`.
- [x] **M** `pyproject.toml` → `[tool.coverage.run]` with `source =
  ["src/debate"]`; gate `--cov-fail-under=80` on the deterministic core
  (PLAN §7.3).
- [x] **S** Add a `scripts/dev.py` helper (`uv run python scripts/dev.py
  {lint|test|run}`) so the menu can invoke each step uniformly.

### P0.3 Config & Secrets Skeleton

- [x] **M** Create `config/debate.json` with the exact keys listed in
  PRD §8 (`rounds`, `model`, `temperature`, `max_tokens_per_turn`,
  `max_tokens_per_debate`, `max_usd_per_debate`,
  `max_requests_per_minute`, `heartbeat_sec`, `heartbeat_timeout_sec`,
  `max_restarts_per_child`, `max_message_bytes`, `search.*`). Trace: NFR-18.
- [x] **M** Create `config/motions.json` with ≥ 5 starter motions.
  Trace: FR-1.
- [x] **M** Create `config/prompts/judge.system.txt`,
  `debater.system.txt`, `verdict.schema.json` as empty placeholders with
  a TODO marker. Trace: FR-8, §6.3.
- [x] **M** Create `.env-example` containing **names only** for
  `LLM_API_KEY`, `SEARCH_API_KEY`, `LOG_LEVEL`. Trace: NFR-10.
- [x] **M** `.gitignore` covers `.env`, `runs/`, `.venv/`, `__pycache__/`,
  `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`. Trace: NFR-10.

### P0.4 Defensive / Compliance

- [x] **M** Add a CI-grade pre-commit (or `scripts/dev.py check`) that
  fails if any tracked file matches `LLM_API_KEY=[^ \n]+` or
  `sk-[A-Za-z0-9]{20,}` (basic secret regex). Trace: NFR-11, SC-5.
- [x] **S** Add `LICENSE` (per course policy) and a one-paragraph
  `README.md` stub — full lab report comes in P9.

### P0 — Definition of Done

- [x] `uv sync` succeeds on a clean checkout.
- [x] `uv run python -m debate.main` prints the stub banner.
- [x] `uv run ruff check` and `uv run ruff format --check` are green.
- [x] `uv run pytest -q` returns "no tests ran" (0 errors).
- [x] `git status` shows no tracked `.env`, no `runs/` artefacts.
- [x] Secret-regex scan passes on the working tree.

---

## Phase P1 — JSON Schemas (SDK)

**Goal.** Lock the IPC contract before any transport code exists.
**Exit Criterion (PLAN §8).** Round-trip JSON validates; bad shapes
rejected.

### P1.1 Envelope & Message Models (`src/debate/sdk/schemas.py`)

- [x] **M** Implement `Envelope` (pydantic `BaseModel`) with fields
  `v: int`, `ts: datetime`, `turn_id: int`, `role: Role`,
  `type: MessageType`, `payload: dict`. Trace: PLAN §6.1.
- [x] **M** Implement enums `Role = {judge, pro, con}` and `MessageType`
  covering all 10 types in PLAN §6.2 (`init, prompt, reply, tool_call,
  tool_result, ping, pong, score, verdict, event, shutdown`).
- [x] **M** Implement sub-payload models, one per `MessageType`:
  `InitPayload`, `PromptPayload`, `ReplyPayload`, `ToolCallPayload`,
  `ToolResultPayload`, `PingPayload`, `PongPayload`, `ScorePayload`,
  `VerdictPayload`, `EventPayload`, `ShutdownPayload`. Trace: PLAN §6.2.
- [x] **M** Implement a discriminated-union loader
  `parse_envelope(line: str) -> Envelope` that selects the correct
  sub-payload by `type` and validates strictly (`extra="forbid"`).
- [x] **M** Constant `SCHEMA_VERSION = 1` (architectural constant — the
  only numeric literal allowed in source per NFR-18).
- [x] **M** Helper `serialize(env: Envelope) -> str` that emits **single
  line** UTF-8 JSON terminated by `\n` (FR-4).

### P1.2 Verdict JSON Schema

- [x] **M** Author `config/prompts/verdict.schema.json` exactly as in
  PLAN §6.3 (`winner` enum excludes `"tie"`, `reasons.minItems=3`,
  scores 0–100). Trace: FR-8, SC-2.
- [x] **M** Loader in `schemas.py` validates a Judge reply against this
  JSON Schema and returns a typed `VerdictPayload` or raises
  `VerdictValidationError`.

### P1.3 Defensive Programming

- [x] **M** Reject envelopes with `v != SCHEMA_VERSION` (clear error
  message naming both versions).
- [x] **M** Reject lines whose **byte length** exceeds
  `cfg.max_message_bytes` *before* JSON parsing — defence against payload
  inflation. Trace: NFR-13.
- [x] **M** Reject `ts` values whose skew vs. wall clock exceeds
  ± `cfg.max_clock_skew_sec` (add to config).
- [x] **M** Refuse `\n` characters inside payload strings during
  serialisation (would break line framing).

### P1.4 Tests (`tests/unit/test_schemas.py`)

- [x] **M** Happy-path round-trip for **each** of the 10 message types.
- [x] **M** Reject unknown `type`.
- [x] **M** Reject mismatched `v`.
- [x] **M** Reject oversize line (`max_message_bytes + 1`).
- [x] **M** Reject `verdict.winner == "tie"`.
- [x] **M** Reject `verdict.reasons` with < 3 items, or any item
  shorter than the schema minimum.
- [x] **M** Reject `extra` fields (`extra="forbid"`).
- [x] **M** Reject envelope with embedded `\n` in payload.
- [x] **S** Property test (Hypothesis, optional) for random valid
  envelopes round-tripping byte-identical.

### P1.5 Documentation

- [x] **M** Docstrings on every public model and helper describing the
  message direction (Judge → Child, Child → Judge, internal-only).
- [x] **S** Add a Mermaid sequence excerpt in the module docstring
  showing a typical turn.

### P1 — Definition of Done

- [x] All 10 message types serialise & validate.
- [x] Verdict JSON Schema rejects `"tie"` and short/sparse reasons.
- [x] `tests/unit/test_schemas.py` ≥ 15 cases, all green.
- [x] Coverage of `sdk/schemas.py` ≥ 95 %.
- [x] No magic numbers in `schemas.py` other than `SCHEMA_VERSION`.

---

## Phase P2 — Config, Secrets & Structured Logger

**Goal.** A safe foundation for every downstream module.
**Exit Criterion (PLAN §8).** Config loads; missing keys raise; logger
redacts.

### P2.1 Config Loader (`src/debate/shared/config.py`)

- [x] **M** `Config` pydantic model mirroring `config/debate.json` (PRD §8).
  Strict types, range validators (`rounds >= 1`,
  `0 < temperature <= 2`, `max_usd_per_debate > 0`, etc.).
- [x] **M** `load_config(path: Path) -> Config` reads JSON, then overlays
  `.env` via `python-dotenv`. Env wins over JSON for overlap.
- [x] **M** Fail fast with a single aggregated `ConfigError` listing
  **all** validation issues (not just the first).
- [x] **S** Support `DEBATE_CONFIG=path/to/override.json` env override
  for tests and CI.

### P2.2 Secrets Vault (`src/debate/shared/secrets.py`)

- [x] **M** `get_key(name: str) -> str` — the **only** sanctioned key
  accessor. Raises `MissingSecretError` with the env-var name (never
  the value). Trace: NFR-10.
- [x] **M** `redact(payload: dict|str) -> dict|str` that masks any value
  matching the secret allow-list regex set
  (`LLM_API_KEY`, `SEARCH_API_KEY`, `sk-…`, `Bearer …`). Trace: NFR-11.
- [x] **M** Module-level guard: importing `secrets.py` does **not** read
  any key at import time (no side effects).

### P2.3 Structured Logger (`src/debate/shared/logger.py`)

- [x] **M** JSONL writer: one record per line with fields `ts`, `role`,
  `turn_id`, `event_type`, `tokens_in`, `tokens_out`, `usd_cost`,
  `data`. Trace: NFR-15.
- [x] **M** `Logger.event(name, **fields)` convenience.
- [x] **M** Every write passes through `redact()` first.
- [x] **M** Per-run output directory `runs/<ts>/run.jsonl`, with
  `<role>.stderr.log` siblings. Trace: NFR-9, FR-10.
- [x] **S** Terminal mirror via `rich` (level-coloured) gated by
  `LOG_LEVEL`.

### P2.4 Defensive Programming

- [x] **M** Logger flushes after every write (debate-grade durability
  even on hard crash).
- [x] **M** Logger refuses to open a `runs/` directory outside the
  project root (path traversal guard).
- [x] **M** Config loader rejects unknown top-level keys (forbids drift
  between code and JSON).

### P2.5 Tests

- [x] **M** `tests/unit/test_config.py` — valid config loads; bad ranges
  rejected; aggregated errors; env override wins.
- [x] **M** `tests/unit/test_secrets.py` — `get_key` raises clean error
  when unset; `redact()` masks each pattern; redaction is idempotent.
- [x] **M** `tests/unit/test_logger.py` — JSONL is valid line-by-line;
  secrets in inputs never appear in output bytes; path traversal blocked.

### P2.6 Security Checkpoint

- [x] **M** Audit: `grep -R "os.environ\[" src/` returns hits **only**
  in `secrets.py`. (Centralised key custody — NFR-10.)
- [x] **M** Audit: `grep -R "print(" src/` returns no hits (logger
  only).

### P2 — Definition of Done

- [x] `Config` validates and rejects the 4 required bad-range cases.
- [x] `redact()` masks all 4 secret patterns in a fuzz test.
- [x] Logger writes valid JSONL with redacted payloads, flushed per line.
- [x] All P2 tests green; coverage of `shared/` ≥ 90 %.

---

## Phase P3 — Gatekeeper & Skill Router (Token Economics + Caching)

**Goal.** Lock the **budget envelope** and the **caching layer** so no
downstream module can leak tokens, money, or duplicate work.
**Exit Criterion (PLAN §8).** Budget caps enforced; search cache hits on
repeat query.

### P3.1 Ledger (`src/debate/shared/gatekeeper.py`)

- [x] **M** `Ledger` dataclass: `tokens_in`, `tokens_out`,
  `usd_spent`, `requests`, `started_at`, `requests_window` (deque of
  timestamps for RPM enforcement). Trace: NFR-2, NFR-3.
- [x] **M** Methods `add(usage: Usage)`, `snapshot() -> dict`,
  `would_exceed(estimate: Usage) -> Reason | None`.
- [x] **M** RPM check: count timestamps in the trailing 60 s window;
  reject if `>= cfg.max_requests_per_minute`.

### P3.2 Token Counting

- [x] **M** `estimate_tokens(messages, model) -> int` — use `tiktoken`
  (add via `uv add tiktoken`) keyed by `cfg.model`; fall back to
  `len(text) / 4` heuristic if the encoder is unknown. Document the
  heuristic in the docstring.
- [x] **M** **Pre-call** estimate enforced against `max_tokens_per_turn`
  and `max_tokens_per_debate`; rejected calls **never** dispatch.
- [x] **M** **Post-call** reconciliation: the LLM provider's reported
  `usage` overwrites the estimate in the ledger (truth wins).
- [x] **S** Warn (single log line) if estimate vs. actual diverges by
  > 20 % — feedback signal that the encoder choice is wrong.

### P3.3 USD Conversion

- [x] **M** `config/pricing.json` — per-model `{input_usd_per_1k,
  output_usd_per_1k}`. Versioned alongside code. Trace: NFR-18.
- [x] **M** `price(usage, model) -> Decimal` using `decimal.Decimal`
  (never float — money). Round half-up to 6 dp.
- [x] **M** Reject any model not present in `pricing.json` rather than
  silently charging $0.
- [x] **M** Pre-call USD estimate uses *expected* output tokens =
  `cfg.max_tokens_per_turn`; post-call reconciles to actual.

### P3.4 `Gatekeeper.execute(callable, *, estimate, role, turn_id)`

- [x] **M** Wraps every external call (LLM + search). Single choke-point
  — no module may bypass it. Trace: §4 anti-duplication rule 2.
- [x] **M** Workflow: `would_exceed` → call → `add` actual → log event
  with ledger snapshot → return result.
- [x] **M** On `BudgetExceeded`, emit a `budget_exhausted` event and
  raise; the Judge's FSM catches this at the `any → ABORT` edge
  (PLAN §5).
- [x] **M** On transient provider error (HTTP 5xx / timeout / 429):
  exponential back-off with jitter, capped at `cfg.max_retries` (add to
  config), still accounted in the ledger.

### P3.5 Context Engineering — Select / Write

- [x] **M** `select_context(role, turn_id) -> list[Message]` returns the
  minimal slice: own last reply + opponent's last reply + rolling
  summary. Never the full transcript. Trace: NFR-4.
- [x] **M** `write_summary(role, turn_id, text)` persists to
  `runs/<ts>/summary.<role>.md`, appended turn-by-turn.
- [x] **M** Summary length capped at `cfg.summary_max_tokens` (add to
  config); the Gatekeeper truncates oldest content first.

### P3.6 SkillRouter (`src/debate/shared/router.py`)

- [x] **M** `SkillRouter.register(name, fn)` and
  `dispatch(tool_call: ToolCallPayload) -> ToolResultPayload`.
- [x] **M** Built-in skills: `search` (wraps `SearchClient`),
  `summarise` (wraps LLM with a fixed system prompt), `score` (wraps
  LLM with the scoring rubric).
- [x] **M** **Content-hash cache** for `search`:
  `key = sha256(normalised_query + str(k)).hexdigest()`. Normalisation:
  Unicode-NFC, lower-case, collapse whitespace, strip URL fragments.
  Trace: NFR-5.
- [x] **M** Cache scope = single debate (instance-level dict); on
  `cache hit` mark `cached: true` in the returned `ToolResultPayload`
  and **bypass** the Gatekeeper (zero token + zero RPM cost).
- [x] **M** Cache eviction: bounded to `cfg.search_cache_max_entries`,
  LRU-evicted. Document collision policy (SHA-256 collisions assumed
  impossible at this scale; equal keys imply equal content).

### P3.7 Defensive Programming

- [x] **M** `Gatekeeper.execute` is re-entrancy-safe via a `threading.RLock`
  (the Watchdog thread can also hit it for `ping` accounting).
- [x] **M** All ledger mutations happen inside the lock; `snapshot()`
  returns a deep copy.
- [x] **M** Router refuses unknown skill names with a typed error;
  malformed `ToolCallPayload.args` are rejected before dispatch.

### P3.8 Tests

- [x] **M** `tests/unit/test_gatekeeper.py` —
  - exact-boundary token cap (allow at `cap`, reject at `cap+1`),
  - USD cap with `Decimal` precision,
  - RPM windowing (29 inside, 31 rejects, monotonic clock),
  - `budget_exhausted` event shape,
  - retry/back-off honoured on 429.
- [x] **M** `tests/unit/test_router_cache.py` —
  - identical query → cache hit, `cached=true`,
  - whitespace/case differences normalised to same key,
  - different `k` produces different keys,
  - LRU eviction kicks in at `max_entries+1`,
  - hit bypasses Gatekeeper (assert no ledger delta).
- [x] **S** Concurrency stress: 100 threads dispatch identical query;
  exactly one upstream call observed.

### P3.9 Security & Compliance

- [x] **M** Audit: every outbound HTTPS call originates in
  `sdk/llm_client.py` or `sdk/search_client.py`, **invoked only** via
  `Gatekeeper.execute` (grep for direct `httpx.` outside SDK should be
  empty).
- [x] **M** Audit: cache values are redacted before any log write.

### P3 — Definition of Done

- [x] Ledger maths exact under `Decimal`; no `float` for money.
- [x] Token estimate vs. actual reconciled and logged.
- [x] Cache hit rate ≥ 1 in the duplicate-query test, with zero
  Gatekeeper delta.
- [x] All P3 tests green; coverage of `gatekeeper.py` + `router.py` ≥ 90 %.

---

## Phase P4 — Provider SDKs (LLM + Search)

**Goal.** Thin, swappable wrappers around external providers.
**Exit Criterion (PLAN §8).** Wired through Gatekeeper; integration
test with stubs.

### P4.1 `sdk/llm_client.py`

- [x] **M** `LLMClient(model, temperature, http: httpx.Client)`; single
  public method `chat(messages, max_tokens) -> ChatResult` returning
  `(text, tokens_in, tokens_out, model)`. Trace: PLAN §4.
- [x] **M** `ChatResult` is a frozen dataclass; USD is computed by the
  Gatekeeper from `pricing.json`, **not** by the SDK.
- [x] **M** Provider authentication header sourced via
  `secrets.get_key("LLM_API_KEY")`.
- [x] **M** Request/response logging redacts the `Authorization`
  header.
- [x] **S** Allow `extra_headers` for org IDs etc., still redacted.

### P4.2 `sdk/search_client.py`

- [x] **M** `SearchClient(provider, http)` with `query(text, k) ->
  list[SearchHit]`. `SearchHit` = `(title, url, snippet)`.
- [x] **M** Truncate `snippet` to `cfg.search_snippet_max_chars` (add to
  config) — prompt-injection inflation defence. Trace: NFR-13.
- [x] **M** Strip non-printable / control characters from `title` and
  `snippet`.

### P4.3 Defensive Programming

- [x] **M** Network timeouts: connect + read both from
  `cfg.http_timeout_sec` (add to config). No infinite hangs.
- [x] **M** Map HTTP 429 / 5xx to a typed `TransientProviderError` so
  the Gatekeeper's retry policy can recognise it.
- [x] **M** Map HTTP 4xx (other than 429) to `PermanentProviderError`
  (no retries).

### P4.4 Tests

- [x] **M** `tests/unit/test_llm_client.py` against a `respx` /
  `httpx.MockTransport` — happy path, 429 → transient, 400 → permanent,
  timeout handling.
- [x] **M** `tests/unit/test_search_client.py` — snippet truncation,
  control-char stripping, malformed provider JSON rejected.
- [x] **S** `tests/integration/test_sdk_wired.py` — Gatekeeper +
  LLMClient + stub provider perform one round and ledger is updated
  correctly.

### P4.5 Security Checkpoint

- [x] **M** Audit: API keys never appear in `repr()` of any SDK object
  (`__repr__` overridden where needed).
- [x] **M** Audit: no SDK module imports `os.environ` directly.

### P4 — Definition of Done

- [x] LLMClient + SearchClient run end-to-end against a stub.
- [x] Gatekeeper-mediated integration test passes with realistic ledger
  totals.
- [x] All P4 tests green; `respx` covers the four HTTP outcomes.

---

## Phase P5 — Orchestration (IPC, FSM, Supervisor, Watchdog)

**Goal.** The runtime backbone — multi-process, non-blocking, resilient.
**Exit Criterion (PLAN §8).** FSM unit-tested; Supervisor smoke test
with echo child.

### P5.1 IPC Layer (`src/debate/orchestration/ipc.py`)

- [x] **M** `JsonPipeReader(stream, max_bytes)` — line-buffered reader
  that accumulates partial reads until `\n`; rejects lines exceeding
  `max_bytes`. Trace: NFR-13, FR-4.
- [x] **M** `JsonPipeWriter(stream)` — writes
  `serialize(env) + "\n"` and flushes; raises `BrokenPipeError` cleanly
  on closed peer.
- [x] **M** On Windows / POSIX both: set child pipes to UTF-8
  (`encoding="utf-8"`, `errors="strict"`), `bufsize=1` (line-buffered).
- [x] **M** Handle `BlockingIOError` from non-blocking reads with a
  deadline (`select` on POSIX, `WaitForSingleObject` not required —
  rely on `selectors.DefaultSelector`).
- [x] **M** Partial-read test scenario: child writes 1-byte-at-a-time;
  reader still reconstructs a single envelope.

### P5.2 State Machine (`orchestration/state_machine.py`)

- [x] **M** Implement the FSM from PLAN §5 exactly: states `INIT,
  SPAWNING, OPENING, PRO_TURN, SCORE_PRO, CON_TURN, SCORE_CON,
  NEXT_ROUND, CLOSING, VERDICT, VALIDATE_VERDICT, TIE_BREAK, RECOVER,
  DONE, ABORT`.
- [x] **M** Pure function: `transition(state, event, ctx) -> state`.
  No I/O, no LLM calls — trivially unit-testable.
- [x] **M** `ctx` tracks `round`, `verdict_retries`,
  `restarts_per_role`, `last_outbound_per_role` (for replay on respawn).
- [x] **M** Universal edge: any state → `ABORT` on `budget_exhausted`.
- [x] **M** `is_terminal(state) -> bool` for `{DONE, ABORT}`.

### P5.3 Supervisor (`orchestration/supervisor.py`)

- [x] **M** `Supervisor.spawn(role) -> ChildProc` — launches child via
  `subprocess.Popen([sys.executable, "-m", "debate.agents." +
  role + "_agent"], stdin=PIPE, stdout=PIPE, stderr=PIPE)`.
- [x] **M** Inherited environment **strips** `SEARCH_API_KEY` for
  child processes; only `LLM_API_KEY` passes through. Trace: NFR-12.
- [x] **M** `send(role, env)` / `recv(role, timeout)` route through
  `JsonPipeReader/Writer`.
- [x] **M** stderr drained by a daemon thread that appends to
  `runs/<ts>/<role>.stderr.log`. Trace: NFR-9.
- [x] **M** `terminate(role, grace_sec)`:
  `SIGTERM → wait(grace) → SIGKILL` (POSIX) / `terminate() → kill()`
  (Windows fallback). Trace: NFR-8.
- [x] **M** On Judge shutdown (SIGINT / normal exit), terminate **all**
  children — no orphans. Use `atexit` + signal handlers.

### P5.4 Watchdog (`orchestration/watchdog.py`)

- [x] **M** Dedicated `threading.Thread` ticking every
  `cfg.heartbeat_sec`. Trace: NFR-6, NFR-7.
- [x] **M** Per role: send `ping`, await `pong` with matching
  `turn_id` within `cfg.heartbeat_timeout_sec`.
- [x] **M** Miss policy: `cfg.heartbeat_max_consecutive_misses`
  consecutive misses (add to config; default 2) → invoke `on_miss(role)`
  callback (wired to Supervisor terminate+respawn).
- [x] **M** Restart counter per role; on
  `count > cfg.max_restarts_per_child` emit
  `child_unrecoverable` event and surface to FSM as
  `restarts_exhausted` (PLAN §5.2).
- [x] **M** After respawn the Judge replays the **last outbound** prompt
  for that role (held in `ctx.last_outbound_per_role`).
- [x] **M** Watchdog stops cleanly on `DONE` / `ABORT`; `join(timeout)`
  before final exit to avoid daemon leakage.

### P5.5 Defensive Programming

- [x] **M** All `Popen` paths wrapped in `try/finally` that calls
  `terminate(role)`; no leaked processes even if `__init__` raises.
- [x] **M** All `recv` calls have explicit timeouts (never `None`).
- [x] **M** `BrokenPipeError` from a dead child surfaces as a typed
  `ChildDisconnectedError`, handled by the Watchdog respawn path.
- [x] **M** POSIX signals: install `SIGPIPE → SIG_IGN` so a child crash
  does not kill the Judge with the default handler.

### P5.6 Tests

- [x] **M** `tests/unit/test_state_machine.py` — every edge in PLAN §5
  exercised, including all three `VERDICT` outcomes and the universal
  `budget_exhausted → ABORT`.
- [x] **M** `tests/unit/test_ipc.py` — partial reads (1-byte chunks),
  oversize line rejection, broken-pipe detection, UTF-8 round-trip.
- [x] **M** `tests/integration/test_supervisor_echo.py` — spawn an
  `echo_child` test fixture that echoes envelopes back; Supervisor
  exchanges 10 messages cleanly, then terminates child.
- [x] **M** `tests/unit/test_watchdog.py` — miss → respawn callback
  fires after exactly `max_consecutive_misses`; counter increments;
  exceeds limit → `child_unrecoverable` raised.
- [x] **S** `tests/integration/test_watchdog_kill.py` — spawn echo
  child, `os.kill(child.pid, SIGKILL)` mid-exchange, Watchdog respawns,
  next message succeeds.

### P5.7 Security Checkpoint

- [x] **M** Audit: child env excludes `SEARCH_API_KEY` (assert via
  integration test that reads `os.environ` inside the echo child).
- [x] **M** Audit: stderr capture does not deadlock when child writes
  > 64 KiB of stderr (drainer thread proves it).

### P5 — Definition of Done

- [x] FSM unit tests cover 100 % of edges in PLAN §5.
- [x] Supervisor + echo child round-trip 10 envelopes in CI.
- [x] Watchdog respawn proven against `SIGKILL`.
- [x] No orphan processes after any test exits (verified by a pytest
  fixture that snapshots child PIDs pre/post).

---

## Phase P6 — Agent Hierarchy (Children)

**Goal.** Pro / Con debaters that **only** differ by a single constant.
**Exit Criterion (PLAN §8).** Two children debate via stubbed Judge
driver.

### P6.1 `agents/base_agent.py` (abstract)

- [x] **M** `BaseAgent(role, cfg, gk, llm, reader, writer)`; `run()`
  enters an infinite read-handle-write loop. Trace: PLAN §4.
- [x] **M** `handle(env)` is abstract; subclasses must implement.
- [x] **M** Built-in handling of `ping → pong` and `shutdown → clean
  exit`. Subclasses never override these (anti-duplication rule 1).
- [x] **M** All outbound replies go through `self.send(env)` which
  stamps `ts`, `turn_id`, `role`.
- [x] **M** Uncaught exception in `handle()` → log to stderr + emit
  `event{name="agent_error"}` envelope → exit code 2 (Watchdog will
  respawn).

### P6.2 `agents/debater_agent.py`

- [x] **M** Inherits `BaseAgent`. Adds `STANCE: ClassVar[str]` and a
  `compose_reply(prompt: PromptPayload) -> ReplyPayload` that:
  1. Calls `gk.select_context(role, turn_id)` for the message list,
  2. Optionally issues a `tool_call:search` envelope and awaits the
     `tool_result`,
  3. Calls `gk.execute(llm.chat, ...)` to generate the reply,
  4. Returns a `ReplyPayload` with token counts.
- [x] **M** Stance constant is injected into the system prompt via a
  template in `config/prompts/debater.system.txt` — text only, no
  conditional logic.
- [x] **M** `handle()` dispatches by `MessageType` (init, prompt,
  ping handled by parent).

### P6.3 `agents/pro_agent.py` / `agents/con_agent.py`

- [x] **M** Each file ≤ 10 lines: import `DebaterAgent`, set
  `STANCE = "pro"` / `STANCE = "con"`, `if __name__ == "__main__":
  ProAgent.bootstrap()`.
- [x] **M** `DebaterAgent.bootstrap()` (classmethod): load config,
  build `Gatekeeper` / `LLMClient` / `SkillRouter`, wire
  `JsonPipeReader(sys.stdin.buffer)` /
  `JsonPipeWriter(sys.stdout.buffer)`, call `run()`.

### P6.4 Defensive Programming

- [x] **M** Debater enforces `len(reply.text) > 0` (never send empty
  reply); on empty LLM output, retry once then emit `agent_error`.
- [x] **M** Debater refuses to issue more than
  `cfg.max_tool_calls_per_turn` (add to config; default 2) tool calls
  per prompt — prevents tool-call loops.
- [x] **M** Debater logs (via stderr only — stdout is reserved for IPC)
  any caught exception with traceback.

### P6.5 Tests

- [x] **M** `tests/unit/test_base_agent.py` — `ping → pong` automatic;
  `shutdown` exits cleanly; uncaught exception in `handle` produces the
  expected `agent_error` envelope and exit code.
- [x] **M** `tests/integration/test_debater_stub_judge.py` — a fake
  Judge sends `init` + 3 `prompt` envelopes; Pro and Con each return
  valid `ReplyPayload`s under a stub LLM (deterministic echo).
- [x] **M** Tool-call cap test: rigged LLM returns `tool_call` thrice;
  debater fires exactly 2 then composes a reply.
- [x] **S** Stress test: 50-envelope ping-pong storm; no envelopes
  dropped, no leaked goroutines/threads.

### P6.6 Security Checkpoint

- [x] **M** Audit: child processes never call `secrets.get_key("SEARCH_API_KEY")`
  (search is Judge-proxied — NFR-12).

### P6 — Definition of Done

- [x] Pro & Con files are each ≤ 10 lines, differing only by `STANCE`.
- [x] Debater + stub Judge integration test completes 3 rounds.
- [x] Tool-call cap enforced.
- [x] No `print()` calls anywhere in `agents/`.

---

## Phase P7 — Judge Logic (Orchestrator + Verdict)

**Goal.** The non-trivial brain — driving rounds, scoring, and
guaranteeing a justified non-tie verdict.
**Exit Criterion (PLAN §8).** End-to-end debate produces non-tie
verdict.

### P7.1 `agents/judge_agent.py` — Round Driver

- [x] **M** `JudgeAgent(cfg, gk, llm, supervisor, watchdog, fsm, logger)`.
- [x] **M** `run_debate(motion) -> Verdict`:
  1. `fsm.transition(INIT, start(motion))`.
  2. `supervisor.spawn("pro")`, `supervisor.spawn("con")`.
  3. Loop driving the FSM until `is_terminal(state)`.
  4. Persist final `VerdictPayload` + run summary.
- [x] **M** For every Pro/Con reply: invoke `score` skill via Router
  (separate, cheaper LLM if `cfg.score_model` set) and feed a
  `ScorePayload` to `logger` and the FSM's `ctx`.

### P7.2 Multi-Stage Verdict Validation

- [x] **M** Stage 1 — **Schema validation** of LLM reply against
  `verdict.schema.json` (FR-8, §6.3).
- [x] **M** Stage 2 — **Semantic validation**: `winner ∈ {pro, con}`
  (excluded by schema, double-checked), `reasons` length ≥ 3, no
  reason a verbatim copy of another (Jaccard < 0.9).
- [x] **M** Stage 3 — **Consistency check**: `scores.pro != scores.con`
  *or* the chosen winner has the higher score (no contradiction).
- [x] **M** On any stage failing: re-prompt the Judge **once** with the
  failure reason injected into the system prompt (FR-9). Trace via
  FSM state `VALIDATE_VERDICT → VERDICT (retry==0)`.
- [x] **M** On second failure: transition to `TIE_BREAK`.

### P7.3 Deterministic Tie-Breaker

- [x] **M** `tie_break(history) -> Role`:
  1. Sum all `ScorePayload.score` per role across the debate.
  2. `argmax` wins.
  3. On numerical tie: the role that **spoke last** (`con`) wins.
     Documented in PLAN §6.4 — pure function, fully reproducible.
- [x] **M** Emit a `verdict` envelope with `reasons = ["Tie-breaker:
  cumulative score = …", …]` so the transcript explains the decision.

### P7.4 Select/Write Context Window Management

- [x] **M** Judge calls `gk.select_context("judge", turn_id)` for
  scoring — receives only the latest opponent reply + rolling
  summary, **not** the full transcript. Trace: NFR-4.
- [x] **M** After every round, Judge calls
  `gk.write_summary("judge", turn_id, summary_text)`. The summary is
  generated by the `summarise` skill (Router) and capped at
  `cfg.summary_max_tokens`.
- [x] **M** Scoring prompts never include earlier rounds verbatim —
  only the summary. Verified by a unit test that inspects the prompt
  payload sent to `gk.execute`.

### P7.5 Defensive Programming

- [x] **M** Verdict generation has its own token cap
  `cfg.max_tokens_for_verdict` (add to config) so a runaway Judge
  cannot blow the debate budget on the final call.
- [x] **M** Tie-breaker never raises (empty score history → deterministic
  fallback to `con`, with a logged `event{name="tie_break_empty"}`).
- [x] **M** Judge handles `child_unrecoverable` by entering `ABORT`
  state, **still** writing a partial transcript and a
  `verdict{outcome="aborted"}` event.

### P7.6 Tests

- [x] **M** `tests/unit/test_verdict_validation.py` — schema fail →
  one retry; semantic fail (duplicate reasons) → retry; consistency
  fail (winner=pro, scores show con higher) → retry; success on retry
  → DONE.
- [x] **M** `tests/unit/test_tie_break.py` —
  - asymmetric scores → higher wins,
  - exact tie → `con` wins,
  - empty history → `con` wins with event logged.
- [x] **M** `tests/unit/test_select_write.py` — `select_context`
  returns at most 3 message blocks; full transcript never appears in
  the scoring prompt.
- [x] **M** `tests/integration/test_debate_full.py` — full 10-ping
  debate against a deterministic stub LLM; verdict is non-tie and
  carries ≥ 3 reasons. Trace: SC-1, SC-2.

### P7.7 Security Checkpoint

- [x] **M** Audit: `runs/<ts>/run.jsonl` from the full-debate test
  contains zero matches for the live API key (regex scan).

### P7 — Definition of Done

- [x] Verdict validator handles all three failure modes plus success.
- [x] Tie-breaker is a pure, deterministic function with full coverage.
- [x] Full-debate integration test produces a valid non-tie verdict.
- [x] Scoring prompt size grows ≤ O(1) with round number (Select/Write
  works).

---

## Phase P8 — Terminal Menu & Entry Point

**Goal.** Operator UX — single command, clear menu, live status.
**Exit Criterion (PLAN §8).** Menu launches debate; status panel
updates per turn.

### P8.1 `ui/menu.py`

- [x] **M** Render a numbered menu (via `rich`): **(1)** start debate
  with default config, **(2)** pick a motion from `motions.json`,
  **(3)** enter a custom motion, **(4)** edit runtime tunables
  (`rounds`, `model`, `budget_usd`, `max_tokens_per_turn`),
  **(5)** replay a saved run, **(6)** quit. Trace: FR-1, FR-11, FR-12.
- [x] **M** Edits in option (4) write to an **in-memory** `Config`
  copy; `config/debate.json` on disk is untouched unless the user
  explicitly chooses "save".
- [x] **M** Validate user input at every prompt; reject silently on
  obviously bad values (negative rounds, etc.) with a clear message.

### P8.2 Live Status Panel

- [x] **M** During a debate, render a `rich.Live` panel refreshed after
  every turn with: current speaker, round X / N, cumulative `tokens_in
  / tokens_out`, `usd_spent / max_usd_per_debate`, elapsed wall-clock.
  Trace: NFR-16.
- [x] **M** Panel never prints raw API responses (would clutter and risk
  redaction bypass) — only the structured summary.
- [x] **S** Side-by-side panes for Pro / Con last replies (truncated to
  N chars).

### P8.3 `main.py`

- [x] **M** Argparse: `--config`, `--motion`, `--non-interactive` for
  scripted runs (CI).
- [x] **M** Install signal handlers for `SIGINT` / `SIGTERM` that
  cleanly terminate children (delegates to Supervisor).
- [x] **M** Exit codes: 0 = `DONE`, 2 = `ABORT(budget_exhausted)`,
  3 = `ABORT(child_unrecoverable)`, 1 = unexpected.

### P8.4 Defensive Programming

- [x] **M** Menu never crashes on `Ctrl-C` — traps `KeyboardInterrupt`
  at every prompt and returns to the main menu.
- [x] **M** Replay mode (option 5) is **read-only**: opens
  `runs/<ts>/run.jsonl`, refuses to spawn children, refuses to make
  any HTTP call. Trace: FR-11.

### P8.5 Tests

- [x] **M** `tests/unit/test_menu.py` — option dispatch table covered;
  validation rejects bad inputs; `KeyboardInterrupt` returns cleanly.
- [x] **S** `tests/integration/test_main_smoke.py` —
  `--non-interactive --motion <fixed>` runs a 2-round debate against
  the stub LLM and exits 0.

### P8 — Definition of Done

- [x] Menu covers all 6 options; (4) tunables persist for the next
  run inside the session.
- [x] Live panel renders without flicker under at least 30 turn updates.
- [x] Replay mode never opens a network socket (verified via a
  `httpx.MockTransport` that asserts zero calls).

---

## Phase P9 — Validation, Chaos Engineering & Final Lab Report

**Goal.** Prove every PRD success criterion under adversarial conditions
and ship the lab report.
**Exit Criterion (PLAN §8).** All SC-1..SC-7 from PRD pass.

### P9.1 Integration Test Matrix

- [ ] **M** SC-1 — full 10-ping debate on the default motion within
  budget. (`tests/integration/test_debate_smoke.py`.)
- [ ] **M** SC-2 — verdict is non-tie + ≥ 3 reasons (schema +
  manual review of one real-LLM run).
- [ ] **M** SC-3 — chaos kill (see P9.2).
- [ ] **M** SC-4 — budget abort (see P9.3).
- [ ] **M** SC-5 — secret scan of `runs/` (see P9.4).
- [ ] **M** SC-6 — `ruff` + `pytest` green on clean `uv sync`.
- [ ] **M** SC-7 — replay determinism with cached search.

### P9.2 Chaos Engineering — Process Kills

- [ ] **M** `tests/integration/test_recovery_chaos.py`:
  - spawn debate, wait for `turn_id == 4`,
  - `os.kill(pro_pid, signal.SIGKILL)`,
  - assert Watchdog respawns within `heartbeat_sec *
    max_consecutive_misses + 1`,
  - assert FSM resumes from `PRO_TURN` with replayed prompt,
  - assert final verdict is still emitted.
- [ ] **M** Variant: `SIGKILL` **both** children sequentially; assert
  debate either completes or aborts with `child_unrecoverable` per
  `cfg.max_restarts_per_child`.

### P9.3 Chaos Engineering — Budget Overflow

- [ ] **M** `tests/integration/test_budget_abort.py`:
  - override `max_usd_per_debate: 0.001` and
    `max_tokens_per_debate: 100`,
  - run the menu non-interactively,
  - assert FSM ends in `ABORT`, exit code 2,
  - assert a `budget_exhausted` event was logged with the offending
    ledger snapshot.

### P9.4 Chaos Engineering — Network & Provider Faults

- [ ] **M** Simulated latency: `httpx.MockTransport` that sleeps
  `cfg.http_timeout_sec + 1` → assert SDK raises
  `TransientProviderError` → Gatekeeper retries → succeeds on second
  attempt.
- [ ] **M** Simulated rate-limit: provider returns 429 thrice then 200;
  assert exponential back-off honoured (timing within 20 % tolerance).
- [ ] **M** Simulated bad JSON: stub LLM returns malformed verdict
  twice → assert tie-breaker engaged → debate ends with deterministic
  winner.

### P9.5 Security & Compliance Audit

- [ ] **M** SC-5 scanner: `scripts/scan_secrets.py` greps
  `runs/`, stdout transcript, and `git log -p` against the secret
  regex set; CI fails on any match. Trace: NFR-10, NFR-11.
- [ ] **M** Audit: `pyproject.toml` declares no transitive dep with a
  known CVE (`uv tree` + `pip-audit` or equivalent).
- [ ] **M** Audit: `runs/<ts>/<role>.stderr.log` contains no key
  patterns even when the child crashes mid-call.

### P9.6 Performance Sanity

- [ ] **S** NFR-14 — full debate on default config completes ≤ 10 min
  on a reference laptop (run thrice, take median). Document any miss.

### P9.7 Documentation & Lab Report (`README.md`)

- [ ] **M** Final `README.md` as a lab report containing:
  1. **Overview & Architecture** — embed C4 diagrams from PLAN §3.
  2. **How to run** — `uv sync`, menu walk-through, example session
     transcript (redacted).
  3. **Configuration reference** — table of every key in
     `config/debate.json` and `.env-example`.
  4. **State machine** — embed PLAN §5 diagram; explain recovery and
     tie-break.
  5. **Token economics** — explain Gatekeeper, ledger sample, USD
     conversion table.
  6. **Context Engineering** — Select/Write rationale and Router-Skill
     caching results (hit-rate from a real run).
  7. **Testing strategy** — unit / integration / chaos matrix +
     coverage report.
  8. **Known limitations & future work** — references PRD §10.
- [ ] **M** Update `PROMPTS.md` with a Prompt 7 entry summarising the
  build-out (decisions made during P0–P9, lessons learned).
- [ ] **S** Inline docstring audit: every public class / function in
  `src/debate/` has a one-paragraph docstring.

### P9.8 Release Checklist

- [ ] **M** `uv lock --upgrade` and commit the refreshed `uv.lock`.
- [ ] **M** Tag the commit `hw2-v1.0.0`.
- [ ] **M** Final secret scan returns clean.
- [ ] **M** All checkboxes in this document are `[x]` or explicitly
  marked `[-]` with a written reason in a `WAIVERS.md`.

### P9 — Definition of Done

- [ ] All SC-1..SC-7 from PRD pass in CI.
- [ ] Chaos suite green (process kill, budget abort, latency, 429,
  bad JSON).
- [ ] Lab report renders correctly on GitHub.
- [ ] No open `[ ]` tasks remain (unless waived).

---

## Appendix A — Traceability Matrix (PRD ↔ TODO)

| PRD ID  | Covered in TODO                                   |
|---------|---------------------------------------------------|
| FR-1    | P0.3, P8.1                                        |
| FR-2    | P5.3, P7.1                                        |
| FR-3    | P5.2 (`ROUND_LIMIT`), P7.1                        |
| FR-4    | P1.1, P5.1                                        |
| FR-5    | P3.6, P6.2                                        |
| FR-6    | P3.6 (content-hash cache)                         |
| FR-7    | P1.1 (envelope), P6.1 (`send` stamps)             |
| FR-8    | P1.2, P7.2                                        |
| FR-9    | P7.2, P7.3                                        |
| FR-10   | P2.3, P7.1                                        |
| FR-11   | P8.4                                              |
| FR-12   | P8.1                                              |
| NFR-1/2/3 | P3.1–P3.4                                       |
| NFR-4   | P3.5, P7.4                                        |
| NFR-5   | P3.6                                              |
| NFR-6/7/8 | P5.4                                            |
| NFR-9   | P5.3                                              |
| NFR-10/11 | P2.2, P2.3, P9.5                                |
| NFR-12  | P5.3, P6.6                                        |
| NFR-13  | P1.3, P4.2, P5.1                                  |
| NFR-14  | P9.6                                              |
| NFR-15  | P2.3                                              |
| NFR-16  | P8.2                                              |
| NFR-17  | enforced in every phase (file-size check)         |
| NFR-18  | P0.3, P3.3 (Decimal pricing JSON)                 |
| NFR-19  | P0.2, P9.1                                        |
| SC-1..7 | P9.1                                              |

## Appendix B — Per-File Line-Budget Plan (NFR-17, ≤ 150 LOC)

| File                                           | Target LOC | Rationale                                |
|------------------------------------------------|------------|------------------------------------------|
| `sdk/schemas.py`                               | ~140       | 10 sub-payloads + envelope + validators  |
| `sdk/llm_client.py`                            | ~80        | One chat method + error mapping          |
| `sdk/search_client.py`                         | ~70        | Query + sanitiser                        |
| `shared/config.py`                             | ~100       | Pydantic model + loader                  |
| `shared/secrets.py`                            | ~50        | get_key + redact                         |
| `shared/logger.py`                             | ~90        | JSONL writer + rich mirror               |
| `shared/gatekeeper.py`                         | ~140       | Ledger + execute + select/write          |
| `shared/router.py`                             | ~110       | Skill registry + cache                   |
| `orchestration/ipc.py`                         | ~110       | Reader/writer + selector loop            |
| `orchestration/state_machine.py`               | ~130       | All edges from PLAN §5                   |
| `orchestration/supervisor.py`                  | ~130       | Popen lifecycle + signals                |
| `orchestration/watchdog.py`                    | ~100       | Heartbeat loop + respawn                 |
| `agents/base_agent.py`                         | ~110       | IPC loop + ping/shutdown                 |
| `agents/debater_agent.py`                      | ~120       | Compose + tool-call cap                  |
| `agents/pro_agent.py`                          | ~10        | STANCE constant + bootstrap              |
| `agents/con_agent.py`                          | ~10        | STANCE constant + bootstrap              |
| `agents/judge_agent.py`                        | ~140       | Round driver + verdict pipeline          |
| `ui/menu.py`                                   | ~130       | 6-option menu + live panel               |
| `main.py`                                      | ~80        | Argparse + signals + dispatch            |

If any file exceeds 150 LOC during implementation, split it before the
phase DoD is checked.

## Appendix C — Glossary

- **Ping / Turn** — one envelope exchange. A round = Pro turn + Con turn
  + Judge scoring.
- **Select / Write** — Context-Engineering pattern: select minimal slice
  on read, write rolling summary on completion.
- **Router-Skill** — Skill-dispatch + cache pattern that bypasses the
  Gatekeeper on cache hits.
- **Watchdog** — heartbeat-driven supervisor co-thread.
- **Tie-Breaker** — deterministic rule replacing a missing or invalid
  Judge verdict.
