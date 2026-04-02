# Self-Improvement Baseline Pack v1

Date: 2026-04-02  
Status: Active definition for supervised learning and promotion.

This document defines the exact baseline `aicode` must satisfy before it is trusted to fix, update, and upgrade code beyond tightly supervised edits.

It is an operational gate, not a marketing claim.

Primary companion artifacts:

- Main repo acceptance baseline: `docs/LEARNING_BASELINE_V1.md`
- Flow contract: `docs/COPILOT_LIKE_FLOW_BLUEPRINT.md`
- Core controller: `src/tools/self_improve.py`
- Live learning loop: `src/tools/live_mode.py`
- Decision telemetry: `src/tools/decision_timeline.py`
- Readiness canaries: `src/tools/readiness_suite.py`

---

## 1) What “baseline-ready” means

`aicode` is baseline-ready only when all of these are true:

1. It can describe its own runtime state and capability boundaries honestly.
2. It routes feature requests to repo research first instead of guessing or treating noun phrases as file paths.
3. It can produce bounded self-improvement proposals with explicit file scope.
4. It can apply approved edits, run verification, and roll back on failure.
5. It learns from prompts, outcomes, corrections, and route failures in persistent runtime stores.
6. It passes the acceptance checks below on the real repo and live API surface.

If any gate fails, it stays in supervised mode.

---

## 2) Truthful capability boundary

Current baseline assumptions for this repo:

- `Self-improvement mode`: supervised
- `Repo scope`: whole repo may be proposed
- `Apply scope`: bounded and allowlisted only
- `Runtime learning`: enabled
- `Autonomous multi-agent execution`: **not baseline-ready yet**

Important truth:

- `multi-agent` and `agent route` currently provide planning/routing help.
- They do **not** yet prove real parallel sub-agent execution with isolated ownership, merge, and verification.
- That capability is deferred until a later baseline.

---

## 3) Baseline gates

### Gate A — Runtime Integrity

Goal:

- The extension, server, and Ollama runtime must be inspectable and not silently stale.

Pass criteria:

- Panel/runtime diagnostics show:
  - loaded extension build version/commit
  - server runtime manifest version/commit
  - runtime mode (`installed` vs `development-host`)
  - stale-install or integrity mismatch when applicable
- Installed VSIX bundle hash matches packaged manifest.

Evidence:

- `vscode-extension/src/extension.ts`
- `vscode-extension/src/runtime_support.ts`
- `vscode-extension/scripts/verify_vsix.js`
- `vscode-extension/smoke/build-integrity.test.cjs`

### Gate B — Self-Awareness

Goal:

- `aicode` must know and state what it can do, what it cannot do, and what runtime it is currently using.

Pass criteria:

- Self-awareness output includes:
  - self-improvement mode
  - latest run id/state
  - last accepted run
  - last rollback reason
  - known editable surfaces
  - server status
  - Ollama status
  - web policy
  - executable commands/actions

Evidence:

- `src/tools/chat_engine.py`
- `src/tools/commanding/handlers/ops.py`
- `tests/test_chat_help_summary.py`
- `tests/test_chat_engine.py`

### Gate C — Research-First Routing

Goal:

- Feature requests and actionable unknowns must default to repo research.

Pass criteria:

- Prompts like “Add a Clear Chat button to the VS Code panel” route to `research`.
- Unknown-but-actionable prompts do not fall straight to `clarify`.
- Freshness-sensitive prompts can mark `needs_external_research`.

Evidence:

- `src/tools/commanding/request_parser.py`
- `src/tools/commanding/handlers/repo.py`
- `tests/test_learning_baseline_v1.py`
- `tests/test_routing_regression_buckets.py`

### Gate D — Bounded Edit / Verify / Rollback

Goal:

- `aicode` must prove it can change code safely under supervision.

Pass criteria:

- Self-improvement proposal includes:
  - `run_id`
  - `candidate_summary`
  - `likely_files`
  - `pinned_files`
  - `approved_files`
  - `verification_plan`
- Apply path rejects dirty targets and targets outside the approved allowlist.
- Failed verification triggers rollback and preserves original file content.

Evidence:

- `src/tools/self_improve.py`
- `tests/test_self_improve_controller.py`

### Gate E — Learning Loop

Goal:

- Learning must be persistent, inspectable, and outcome-driven.

Pass criteria:

- Prompt events, retrieval traces, and output traces are persisted.
- Explicit teaching/correction changes later behavior.
- Self-improvement runs record proposal/apply/verified/rollback states.
- Decision telemetry surfaces reroute and research pressure trends.

Evidence:

- `src/tools/learning_events.py`
- `src/app_service.py`
- `src/tools/decision_timeline.py`
- `tests/test_learning_baseline_v1.py`
- `tests/test_learning_events_transparency.py`
- `tests/test_decision_timeline.py`

### Gate F — Live Learning Mode

Goal:

- The system can learn continuously without silently escalating into unsafe autonomous edits.

Pass criteria:

- Default live mode executes the `learn` slice only.
- Additional slices require unlocks and explicit opt-in.
- Live state is persisted and bounded iterations work deterministically.

Evidence:

- `src/tools/live_mode.py`
- `src/main.py`
- `tests/test_live_mode.py`
- `tests/test_main_cli_decision_timeline.py`

---

## 4) Promotion ladder

`aicode` should move through these states in order:

### Level 0 — Observe Only

- Can answer, summarize, research, and log learning signals.
- No self-applied code changes.

### Level 1 — Learning Only

- `live` mode allowed.
- Can improve ranking, memory, traces, and proposal quality.
- Still no unsupervised code apply.

### Level 2 — Supervised Single-File Fix

- Can propose and apply one bounded change on approved files.
- Must verify and roll back when needed.

### Level 3 — Supervised Multi-File Fix

- Can apply bounded multi-file changes within explicit allowlists.
- Must pass targeted verification and readiness.

### Level 4 — Restricted Autonomous Repair

- Future state only.
- Requires successful proof of real worker/sub-agent execution, task ownership, merge safety, and repeated pass rate over a fixed evaluation set.

Current repo target:

- Promote to and operate at **Level 2 / Supervised Single-File Fix**
- Keep Levels 3 and 4 behind future gates

---

## 5) Exact baseline acceptance commands

Run these from repo root:

```bash
./.venv/bin/python -m pytest -q tests/test_learning_baseline_v1.py
./.venv/bin/python -m pytest -q tests/test_self_improve_controller.py
./.venv/bin/python -m pytest -q tests/test_chat_help_summary.py tests/test_chat_engine.py
./.venv/bin/python -m pytest -q tests/test_live_mode.py tests/test_decision_timeline.py tests/test_main_cli_decision_timeline.py
./.venv/bin/python -m pytest -q tests/test_server_app_command.py tests/test_server_learning_metrics.py
./.venv/bin/python -m pytest -q
npm --prefix vscode-extension run compile:clean
npm --prefix vscode-extension run test:smoke
npm --prefix vscode-extension run verify:vsix
curl -sS http://127.0.0.1:8005/healthz
```

Live API checks that must behave correctly:

```bash
curl -sS -X POST http://127.0.0.1:8005/v1/aicode/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"Add a Clear Chat button to the VS Code panel"}'

curl -sS -X POST http://127.0.0.1:8005/v1/aicode/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"self-improve status"}'

curl -sS http://127.0.0.1:8005/v1/aicode/readiness
```

Expected outcomes:

- feature request routes to `research`
- self-improvement status is populated
- readiness passes or reports exact failing canary
- extension build integrity checks pass

---

## 6) What unlocks editing authority

`aicode` may start fixing/updating code in the repo baseline workflow when:

1. Gates A-F all pass.
2. The live API checks pass.
3. The current workspace is not in a stale runtime state.
4. The proposal has explicit approved files.
5. The target files are not already dirty from unrelated work.

If any of those are false, it may still:

- research
- explain
- propose
- learn
- ask for approval

but it should not self-apply.

---

## 7) What still does not count as proven

These are intentionally **not** considered baseline-complete yet:

- freeform autonomous repo-wide refactors
- dependency or schema migration autonomy
- unsupervised multi-file repair across unrelated surfaces
- true parallel worker/sub-agent execution
- automatic promotion from supervised to autonomous without passing a stronger eval pack

That keeps the baseline honest and protects the repo from overclaiming.
