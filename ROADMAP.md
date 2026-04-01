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

- [ ] 8) Fast file indexing (tree, language, size, ownership)
- [ ] 9) Symbol index (functions/classes/usages)
- [ ] 10) Semantic retrieval for relevant code chunks
- [ ] 11) Context-packing strategy with token budgeting
- [x] 12) Change-impact analysis (MVP: traceback + test companion file awareness in repair planner)
- [ ] 13) "Read first, edit second" policy enforcement

## Phase 3 — Safe Change Engine

- [x] 14) Add true unified-diff patch mode (MVP-adjacent: multi-file rewrite apply mode + related-file planning)
- [ ] 15) Patch validation (reject malformed/unsafe diffs)
- [ ] 16) Conflict detection and automatic rebase/retry strategy
- [ ] 17) Rollback snapshots for every apply operation
- [ ] 18) Workspace boundary and command allowlist hardening
- [ ] 19) Secret leak and dangerous command detection before execution

## Phase 4 — Autonomous Verify-and-Fix Loops

- [x] 20) Targeted test selection based on changed files (MVP: `src/<name>.py` -> `tests/test_<name>.py`)
- [x] 21) Failure parser (MVP categories: timeout/syntax/dependency/assertion/type/name/runtime/unknown)
- [x] 22) Automated repair loop (MVP: single-file edit → test command → repair up to N attempts + rollback)
- [x] 23) Root-cause classification (MVP strategy routing by failure category, including flaky signals)
- [x] 24) Exit policy: stop conditions + high-quality blocker report (MVP blocker JSON + rollback)
- [x] 25) Auto-generate minimal repro for persistent failures

## Phase 5 — Developer Workflows Parity

- [ ] 26) Multi-mode assistant actions: explain, implement, refactor, optimize, secure
- [x] 27) Terminal copilot mode (MVP command loop: help/plan/generate/edit/capabilities)
- [ ] 28) Debug assistant mode (breakpoints/stack/variables guidance)
- [ ] 29) Notebook assistant mode (cell edit/run/fix loop)
- [ ] 30) Documentation assistant mode (README/changelog/API updates from code changes)
- [ ] 31) Task planner mode with visible checklist and progress updates

## Proof Log (latest)

- `python -m pytest -q` → `10 passed` before terminal UI, then expanded tests after UI changes.
- `python -m src.main capabilities` returned configured capability flags.
- `python -m src.main plan "Edit src/main.py to add argparse support"` returned structured `AgentAction(...)`.
- `python -m src.main edit ... --yes` successfully previewed and applied patch in workspace.
- `python -m src.main autofix <file> "<instruction>" --tests "python -m pytest -q" --max-attempts 3` now runs iterative repair with rollback on failure.
- `python -m pytest -q` now passes with expanded coverage (`17 passed`).
- Forced-failure proof: `python -m src.main autofix .tmp_rollback_demo.py "Set x to 999" --tests "python -c \"import sys; sys.exit(1)\"" --max-attempts 1` prints rollback and file remains `x = 1`.
- New five-at-once proof: full suite now passes `23 passed`; targeted autofix selected `python -m pytest -q tests/test_tempmod.py`, emitted JSON trace logs with trace IDs, and forced failure created `.autofix_reports/<trace_id>.json` before rollback.
- New five-at-once proof #2: prompt layering is active (`system` + `developer` + `tool` + `user`), provider retries with backoff, audit export available via `python -m src.main audit <trace_id>`, and failed autofix runs now emit both blocker JSON and `_repro.md` minimal repro artifacts.
- New five-at-once proof #3: flaky detection categorizes `flaky rerun happened`, repair planner returns related files, pytest node IDs are extracted into focused repro steps, and fix-memory retrieval returns similar past attempts.
- New ten-at-once proof: `autofix --multi` used planned companion files, `--no-flaky-confirm` changed flaky handling, `blocker` and `memory` commands returned structured data, confidence scores were emitted, and full suite passes (`43 passed`).

## Phase 6 — Learning System (Do More Each Time)

- [ ] 32) Persistent project memory (decisions, conventions, gotchas)
- [x] 33) Fix memory (MVP persistent JSONL store + retrieval hints by target/category)
- [ ] 34) Prompt optimization from outcome data (A/B strategy)
- [ ] 35) Tool policy learning (which tools to call first by task type)
- [ ] 36) "Similar issue retrieval" before starting new repairs
- [x] 37) Confidence scoring + automatic escalation thresholds (MVP confidence scoring per attempt/result)

## Phase 7 — Product Quality and Ops

- [ ] 38) End-to-end evaluation suite (golden tasks and expected outcomes)
- [ ] 39) Regression CI gate (block degraded behavior)
- [ ] 40) Performance and cost budgets per workflow
- [ ] 41) Telemetry dashboard (success, retries, failure categories)
- [ ] 42) Versioned releases with migration notes
- [ ] 43) Crash-safe state and resumable tasks

## Phase 8 — Governance, Security, and Team Scale

- [ ] 44) Role-based approval policies (auto-apply vs review-required)
- [ ] 45) Audit logs for prompts, tool calls, patches, and outcomes
- [ ] 46) Dependency and license scanning before merge
- [ ] 47) Data retention and privacy controls
- [ ] 48) Team playbooks (incident response, rollback, hotfix protocols)

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
