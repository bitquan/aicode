# Coding AI Master Roadmap

This plan is designed to make the assistant increasingly autonomous over time: less manual coding by you, more automatic implementation + validation + fixing by the agent.

## North Star

Build a local-first coding assistant that can:

1. Understand a task in natural language.
2. Find the right code context in your repo.
3. Propose and apply safe code changes.
4. Run tests/lint/build and diagnose failures.
5. Self-correct in loops until success or clear blocker.
6. Learn from previous fixes to improve next runs.

## Success Metrics (track every sprint)

- Task success rate (fully completed tasks / total tasks)
- First-pass success rate (completed without repair loop)
- Mean repair iterations per task
- Time-to-green (request to passing tests)
- Human edits after agent apply (lower is better)
- Regression rate after agent changes
- Cost and latency per successful task

---

## Phase 0 — Foundation (Done/Now)

- [x] Local Ollama model integration
- [x] Prompt-based code generation
- [x] Basic code evaluation runner
- [x] Safe file rewrite + diff preview + apply
- [x] Initial tests for core flows

## Phase 1 — Reliable Core Agent

- [x] 1) Capability matrix and scope definition (chat, edit, fix, test, explain, refactor)
- [x] 2) Model provider abstraction (Ollama + optional cloud fallback)
- [x] 3) Strict structured outputs for agent actions (JSON schema)
- [x] 4) Centralized configuration (profiles for local/dev/prod)
- [x] 5) Better prompt orchestration (system/developer/user/tool context layers)
- [x] 6) Retry + backoff + circuit-breaker for model/tool failures (MVP: provider retry/backoff)
- [x] 7) Unified logging and trace IDs across every agent run (MVP: autofix trace logs + trace IDs)

## Phase 2 — Repo Intelligence

- [x] 8) Fast file indexing (tree, language, size, ownership)
- [x] 9) Symbol index (functions/classes/usages)
- [x] 10) Semantic retrieval for relevant code chunks
- [x] 11) Context-packing strategy with token budgeting
- [x] 12) Change-impact analysis (MVP: traceback + test companion file awareness in repair planner)
- [x] 13) "Read first, edit second" policy enforcement

## Phase 3 — Safe Change Engine

- [x] 14) Add true unified-diff patch mode (MVP-adjacent: multi-file rewrite apply mode + related-file planning)
- [x] 15) Patch validation (reject malformed/unsafe diffs)
- [x] 16) Conflict detection and automatic rebase/retry strategy (MVP: conflict helper)
- [x] 17) Rollback snapshots for every apply operation
- [x] 18) Workspace boundary and command allowlist hardening (MVP: guarded test command execution)
- [x] 19) Secret leak and dangerous command detection before execution (MVP: dangerous-token command guard)

## Phase 4 — Autonomous Verify-and-Fix Loops

- [x] 20) Targeted test selection based on changed files (MVP: `src/<name>.py` -> `tests/test_<name>.py`)
- [x] 21) Failure parser (MVP categories: timeout/syntax/dependency/assertion/type/name/runtime/unknown)
- [x] 22) Automated repair loop (MVP: single-file edit → test command → repair up to N attempts + rollback)
- [x] 23) Root-cause classification (MVP strategy routing by failure category, including flaky signals)
- [x] 24) Exit policy: stop conditions + high-quality blocker report (MVP blocker JSON + rollback)
- [x] 25) Auto-generate minimal repro for persistent failures

## Phase 5 — Developer Workflows Parity

 - [x] 26) Multi-mode assistant actions: explain, implement, refactor, optimize, secure (MVP: `mode` command)
 - [x] 27) Terminal copilot mode (MVP command loop: help/plan/generate/edit/capabilities)
 - [x] 28) Debug assistant mode (MVP guidance via `debug-guide` command)
 - [x] 29) Notebook assistant mode (MVP guidance via `notebook-guide` command)
 - [x] 30) Documentation assistant mode (MVP via `doc-update` summary generation)
 - [x] 31) Task planner mode with visible checklist and progress updates (MVP via `task-plan`)

## Phase 6 — Learning System (Do More Each Time)

- [x] 32) Persistent project memory (MVP: JSONL notes via `project-memory` commands)
- [x] 33) Fix memory (MVP persistent JSONL store + retrieval hints by target/category)
- [x] 34) Prompt optimization from outcome data (MVP strategy score tracking + selection)
- [x] 35) Tool policy learning (MVP command outcome tracking + recommendation)
- [x] 36) "Similar issue retrieval" before starting new repairs (MVP preflight hints in autofix)
- [x] 37) Confidence scoring + automatic escalation thresholds (MVP confidence scoring per attempt/result)

## Phase 7 — Product Quality and Ops

- [x] 38) End-to-end evaluation suite (MVP: `eval` command for capability checks)
- [x] 39) Regression CI gate (MVP: `gate` command executes tests + eval checks)
- [x] 40) Performance and cost budgets per workflow (MVP: `budget show|set|check|metrics` + runtime metric recording)
- [x] 41) Telemetry dashboard (MVP: `telemetry` summary command)
- [x] 42) Versioned releases with migration notes (MVP: `release-notes` generator)
- [x] 43) Crash-safe state and resumable tasks (MVP: persisted autofix state + `resume-autofix`)

## Phase 8 — Governance, Security, and Team Scale

- [x] 44) Role-based approval policies (MVP: `policy-check`, edit auto-apply role guard)
- [x] 45) Audit logs for prompts, tool calls, patches, and outcomes (MVP: audit export command)
- [x] 46) Dependency and license scanning before merge (MVP: `license-scan` and compliance summary)
- [x] 47) Data retention and privacy controls (MVP: `retention-clean`)
- [x] 48) Team playbooks (MVP scaffold/status commands and templates)

## Proof Log (latest)

- `python -m pytest -q` passes (`67 passed`).
- `python -m src.main gate` returns `passed: True` (tests + eval checks).
- `python -m src.main telemetry` returns trace/event/fix-memory summary.
- `python -m src.main deps` returns dependency inventory from `pyproject.toml`.
- `python -m src.main policy-check edit --role developer --auto` correctly blocks auto-apply.
- `python -m src.main playbooks scaffold` created incident/rollback/hotfix playbooks under `docs/playbooks`.
- `python -m src.main budget show|check` returned configured thresholds and pass/fail checks.
- `python -m src.main license-scan` and `python -m src.main compliance` both passed on current dependencies.
- `python -m pytest -q` now passes (`72 passed`).
- `python -m src.main cost-estimate 1000 500` returns deterministic USD estimate based on configurable token rates.
- `python -m src.main incident-timeline <trace_id>` and `incident-report <trace_id>` generate timeline/report artifacts from audit traces.
- `python -m pytest -q` now passes (`75 passed`).
- `python -m src.main benchmark` returns a check-based readiness score.
- `python -m src.main status` returns consolidated roadmap/benchmark/budget/compliance posture.
- `python -m src.main status-export` writes `.autofix_reports/status/latest_status.md`.

---

## Missing Gaps Covered in This Plan

These are commonly missed in early agent projects and are now explicitly included:

- Structured outputs and schema validation
- Repair stop conditions and blocker quality
- Fix memory and retrieval of past successful repairs
- Regression gates and benchmark tasks
- Rollback, auditability, and approval policies
- Cost/latency controls and budgets
- Crash-safe resumability

---

## Self-Improvement Operating Loop (Core Requirement)

Use this loop on every task to increase autonomy over time:

1. Understand goal and constraints.
2. Retrieve relevant code + past similar fixes.
3. Plan edits with risk assessment.
4. Apply minimal patch.
5. Run verification (tests/lint/type/build).
6. If fail, classify root cause and repair.
7. Store what worked/failed in fix memory.
8. Update strategy weights for next task.

This is the mechanism that shifts your workload from writing code to reviewing and approving higher-quality automated changes.

---

## Implementation Order (recommended)

1. Phase 1 + Phase 3 (reliable + safe edit engine)
2. Phase 4 (autonomous verify-and-fix loops)
3. Phase 2 (repo intelligence depth)
4. Phase 6 (learning flywheel)
5. Phase 5 then Phase 7/8 (workflow parity and scale)

---

## Definition of Done for "Copilot-Like"

Consider parity achieved when:

- 80%+ routine coding tasks complete with no manual code writing.
- 70%+ fixes are resolved by automated repair loops.
- Agent can safely modify multi-file changes with passing verification.
- Human role is mostly approve/review/escalate, not implement from scratch.
