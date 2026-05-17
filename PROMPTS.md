# AI-Assisted Development Log (PROMPTS.md)
## HW1 — Signal Frequency Extraction using Neural Networks
## HW2 — AI Agent Debate (Multi-Process Orchestration)

| Field    | Value               |
|----------|---------------------|
| Version  | 2.00                |
| Updated  | 2026-05-17          |

---

## Purpose

This document records all significant AI-assisted development interactions, their context, purpose, output summaries, and lessons learned.  It provides transparency about AI contributions and supports reproducibility of the development process.

---

## Prompt 1 — Full Project Bootstrap

**Tool:** Augment Agent (Claude Sonnet 4.6)  
**Date:** 2026-04-28  
**Context:** Empty workspace, complete project specification provided.

**Prompt Summary:**
```
You are a Senior Software Architect... [full system prompt with 22 rules]
PROJECT DETAILS: HW1 — Signal Frequency Extraction using Neural Networks
[Full project specification with theoretical background, dataset spec,
network architectures, requirements checklist, and success criteria]
```

**Purpose:** Bootstrap the entire project from scratch — documentation, scaffolding, implementation, tests, and final validation.

**Output Summary:**
- Created docs/PRD.md (full product requirements, 15 sections)
- Created docs/PLAN.md (C4 diagrams, ADRs, data schemas, module map)
- Created docs/TODO.md (44 tasks across 8 phases with priorities)
- Created docs/PRD_signal_generation.md (signal generation subsystem PRD)
- Created docs/PRD_models.md (MLP, RNN, LSTM architecture specifications)
- Created docs/PRD_training.md (loss, optimizer, early stopping, checkpointing)
- Created docs/PROMPTS.md (this file)
- Created all config/*.json, pyproject.toml, .env-example, .gitignore
- Implemented full Python package: data_service, mlp/rnn/lstm models, training_service, evaluation_service, sdk, main.py
- Created comprehensive test suite: unit + integration tests
- Ran experiments: trained all 3 models, generated all result plots
- Final README as complete lab report

**Iterations:** 1 major prompt with iterative file-by-file refinement

**Key Design Decisions Made by AI:**
1. Frequencies: 5, 15, 30, 50 Hz — covers 3 octaves, max 50 Hz → 200 Hz sampling rate.
2. Tanh activations for MLP (bounded sinusoidal outputs).
3. Adam optimizer for all models (reduces confounding variables).
4. Gradient clipping max_norm=1.0 (prevents RNN exploding gradients).
5. Gatekeeper wraps file I/O (architecture compliance + future extensibility).
6. ReduceLROnPlateau scheduler (adaptive without fixed schedule).

**Lessons Learned:**
- Documentation-first discipline forces careful architecture thinking before coding.
- Fixed seeds must be set in 4 places (torch, numpy, random, cudnn) for full reproducibility.
- File-size limits (150 lines) require splitting models into separate files.
- Tanh > ReLU for bounded regression targets (sinusoidal signals).

---

## Prompt 2 — Architecture Clarification

**Tool:** Augment Agent (in-context refinement)  
**Date:** 2026-04-28  
**Context:** Deciding how to handle Gatekeeper for a project with no external APIs.

**Question Asked:**
"The architecture rules require a Gatekeeper for all external API calls, but this project has no external APIs. How should the Gatekeeper be implemented?"

**Resolution:**
The Gatekeeper was implemented to wrap all file I/O operations (dataset save/load, checkpoint save/load, results save).  This satisfies the architecture rule while being practically meaningful — file operations can fail transiently (disk full, locked files) and benefit from retry logic and logging.  The Gatekeeper is also designed as an extension point for future remote storage adapters.

**Output:** `src/freq_extractor/shared/gatekeeper.py` with execute(), retry logic, and get_queue_status().

---

## Prompt 3 — Test Design

**Tool:** Augment Agent (in-context)  
**Date:** 2026-04-28  
**Context:** Writing unit tests for signal generation with FFT verification.

**Key Insight:**
Tests for signal correctness use `scipy.fft` to verify that the dominant frequency in the generated signal matches the configured frequency.  This is a white-box test that validates the mathematical correctness of the generated data, not just its shape.

**Test Pattern Used:**
```python
freqs = scipy.fft.rfftfreq(n_samples, d=1/sampling_rate)
magnitudes = np.abs(scipy.fft.rfft(signal))
dominant_freq = freqs[np.argmax(magnitudes)]
assert abs(dominant_freq - expected_freq) < 0.5  # within 0.5 Hz
```

---

## Prompt 4 — Hyperparameter Justification

**Tool:** Augment Agent (in-context)  
**Date:** 2026-04-28  
**Context:** Documenting rationale for all hyperparameter choices.

**Decisions Documented:**

| Hyperparameter | Value | Justification |
|----------------|-------|---------------|
| Hidden size    | 64    | Balances expressivity and training speed; 3× input features |
| Num layers     | 2     | Hierarchical abstraction; 3+ layers risk vanishing gradients in RNN |
| Batch size     | 64    | Stable gradient estimates; fits in RAM; standard for small datasets |
| Learning rate  | 0.001 | Adam paper default; empirically validated for sequence models |
| Max epochs     | 300   | Generous upper bound; early stopping prevents waste |
| ES patience    | 20    | 20 × batch_iterations ≈ enough to escape local plateaus |
| Dropout        | 0.1   | Light regularization; dataset is small (7960 entries) |
| Grad clip      | 1.0   | Standard for RNNs; prevents gradient explosion in BPTT |

---

## Best Practices Identified

1. **Documentation before code**: PRD → PLAN → TODO → code dramatically reduces rework.
2. **Config-driven everything**: Changing an experiment requires only editing JSON, not source code.
3. **Fixed seeds everywhere**: torch + numpy + random + cudnn for true reproducibility.
4. **Separate model files**: Keeping MLP, RNN, LSTM in separate files respects 150-line limit.
5. **TDD mindset**: Writing test scenarios in PRDs before implementation guides better API design.
6. **Gatekeeper pattern**: Even for file I/O, centralizing operations enables consistent logging.
7. **Tanh for regression on bounded signals**: ReLU can produce unbounded outputs; Tanh is safer.
8. **Gradient clipping**: Always clip gradients in RNN/LSTM training to prevent divergence.

---

## Prompt 5 — UI Refinement and Final Validation

**Tool:** Codex
**Date:** 2026-05-01
**Context:** Completing the Sinusoid Explorer UI, Phase 8 audit tasks, edge cases, and data validation rows.

**Prompt Summary:**
The user requested that the local Dash app run at `127.0.0.1:8765`, that the Sin 1-4 controls be restored to the left dashboard rail, that each sinusoid slider/handle use its assigned color, and that remaining TODO sections be executed and marked done only after verification.

**Resolution:**
- Updated UI layout and CSS so the sidebar remains on the left and Sin 1-4 controls use cyan/red/green/yellow styling.
- Added defensive validation for empty datasets, config schema/ranges, CUDA OOM fallback, and dataset integrity.
- Added regression tests for edge cases, data validation, documentation quality, and UI structure.
- Updated `docs/TODO.md` after focused tests, full pytest coverage, Ruff, and line-count checks passed.

**Lessons Learned:**
- Browser-facing UI work needs both unit tests and visual/manual startup checks.
- TODO rows are only useful when tied to executable checks or concrete documents.
- Gatekeeper audits need a clear bootstrap boundary for config-file reads.

---

## Prompt 6 — HW2 Project Bootstrap

**Tool:** Augment Agent (Claude Opus 4.7)
**Date:** 2026-05-17
**Context:** Empty HW2 workspace, transitioning from HW1's neural-network signal extraction
domain into a multi-process **agentic orchestration** domain. The new project requires a
Parent (Judge) process supervising two Child (Pro / Con) LLM agents that conduct a structured
10-ping debate with internet-search capability, JSON-framed IPC, and a mandatory
non-tie verdict.

**Prompt Summary:**
```
You are a Senior Software Architect. Bootstrap HW2 — AI Agent Debate based on the lecture
notes. Produce:
  1. Updated PROMPTS.md (this entry).
  2. docs/PRD_HW2.md  — professional product requirements document.
  3. docs/PLAN_HW2.md — implementation plan with C4 diagrams, OOP hierarchy,
     state machine, tooling (uv/ruff/pytest), and JSON schema.
Constraints: Gatekeeper (budget/token caps), Watchdog (keep-alive recovery),
config-driven (JSON/ENV) — no hardcoded values, terminal menu interface.
Design must follow Context Engineering: Select/Write context-window management
and Router-Skill / caching for token economy.
```

**Purpose:** Establish architectural foundation for HW2 before writing any executable code —
locking down the IPC contract, the supervision model, the budget/safety envelope, and the
project layout so subsequent implementation prompts have an unambiguous target.

**Output Summary:**
- Updated `PROMPTS.md` — bumped header to v2.00, registered HW2 scope, added this entry.
- Created `docs/PRD_HW2.md` — system overview, functional and non-functional requirements,
  success criteria, and traceability for the Judge / Pro / Con triad.
- Created `docs/PLAN_HW2.md` — C4 context + container diagrams, OOP class hierarchy
  (SDK layer → `BaseAgent` → `JudgeAgent` / `DebaterAgent` → `ProAgent` / `ConAgent`),
  debate state machine, JSON IPC schema, and the `uv` / `ruff` / `pytest` toolchain plan.

**Domain Transition — HW1 → HW2:**

| Axis                | HW1 (Signal Extraction)              | HW2 (Agent Debate)                          |
|---------------------|--------------------------------------|---------------------------------------------|
| Compute primitive   | PyTorch tensors, MLP/RNN/LSTM        | LLM API calls (chat completions + tools)    |
| Concurrency model   | Single-process training loop         | Multi-process: Parent + 2 Children over IPC |
| Gatekeeper guards   | File I/O retry & logging             | Token budget, RPM/RPS caps, API-key vault   |
| Failure mode        | NaN loss, divergence                 | Stuck child, rate-limit, runaway tokens     |
| Recovery mechanism  | Early stopping, grad clip            | Watchdog keep-alive + child respawn         |
| Output artifact     | Frequency predictions + plots        | Structured debate transcript + verdict JSON |
| External dependency | None                                 | LLM provider + web-search tool              |

**Key Design Decisions Made by AI:**
1. **Process topology** — Parent (Judge) owns two `subprocess.Popen` children communicating
   over line-delimited JSON on stdin/stdout (pipe IPC). Rationale: zero broker dependency,
   trivially testable, OS-level isolation so a crashed debater never kills the Judge.
2. **OOP layering** — A thin `LLMClient` SDK wraps the provider; `BaseAgent` owns the
   IPC loop and Gatekeeper hooks; `DebaterAgent` adds search + stance prompt; `ProAgent`
   and `ConAgent` only inject a stance constant. Zero duplicated transport code.
3. **10-ping cycle** — Hard-bounded by the Judge's state machine (`ROUND_LIMIT = 10`),
   not by the children, so a misbehaving child cannot extend the debate.
4. **Mandatory non-tie verdict** — Judge prompt schema forbids `"winner": "tie"`; the
   reply is re-asked once and then resolved by a deterministic tie-breaker rule.
5. **Context Engineering — Select/Write** — Each agent receives only the *selected*
   slice of context it needs (own stance + last opponent ping + scratchpad summary),
   never the full transcript; the Judge *writes* a rolling summary back to disk.
6. **Router-Skill caching** — Search queries are routed through a content-hashed cache;
   identical queries within a debate reuse cached results, cutting token + API spend.
7. **Watchdog** — Parent thread pings each child every `HEARTBEAT_SEC`; missed beats
   trigger `terminate → respawn → replay last prompt` with an attempt counter.
8. **Config-driven** — `config/debate.json` + `.env` hold every tunable (model name,
   round count, token caps, heartbeat interval, search provider); no magic numbers
   live in source.

**Lessons Learned (carried from HW1):**
- Documentation-first discipline (PRD → PLAN → code) is even more critical when the
  runtime is non-deterministic (LLMs), because it pins down the *contract* the tests
  will enforce.
- Gatekeeper pattern generalises cleanly from "file I/O" (HW1) to "external API +
  token budget" (HW2) — same execute/retry/log skeleton, different policy.
- The 150-line-per-file rule continues to apply; the OOP hierarchy is designed so
  each concrete agent file stays small.

---
