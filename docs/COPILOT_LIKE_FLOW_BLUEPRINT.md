# AICode Copilot-Like Flow Blueprint

Date: 2026-04-02  
Purpose: Define how `aicode` should process user prompts, reason, research unknowns, and execute tasks with high reliability.

This document is an implementation target for this repo. It is **Copilot-like behavior guidance**, not a claim about proprietary internals.

Primary baseline contract: `docs/LEARNING_BASELINE_V1.md` (Main Baseline v1).
UI/UX execution companion: `docs/UI_UX_REDESIGN_PLAN_V1.md`.

---

## Repo Coverage Map (Whole Repo)

This flow applies across all major repository surfaces:

- CLI and command entry (`src/main.py`)
- Chat orchestration and routing (`src/tools/chat_engine.py`)
- API service path (`src/server.py`, app service layer)
- Tooling modules (`src/tools/*`)
- Provider/config/prompt layers (`src/providers`, `src/config`, `src/prompts`)
- VS Code extension UX (`vscode-extension/`)
- Verification surface (`tests/`)
- Operations and governance docs/playbooks (`docs/`)

The flow blueprint defines **how** decisions are made; Main Baseline v1 defines **what** must be true for acceptance.

---

## 1) North-Star Behavior

For every user request, `aicode` should:

1. Understand intent and constraints.
2. Gather the best available evidence (repo first, web when needed).
3. Reason over options and choose a safe plan.
4. Execute via tools/code edits.
5. Verify outcomes (tests/build/lint where relevant).
6. Return a concise, actionable answer with uncertainty clearly stated.

---

## 2) End-to-End Request Flow

## Stage A — Prompt Intake & Normalization

- Capture raw prompt and context (workspace, active file, run state, prior turns).
- Normalize prompt (intent keywords, entities, files, symbols, constraints, deadlines).
- Classify request type:
  - question/explanation
  - code change
  - debug/fix
  - design/architecture
  - ops/run/build/test
- Detect ambiguity and risk early.

Output: `request_profile` with intent, confidence, risk level, and required evidence.

## Stage B — Intent Routing + Task Planning

- Route to the correct workflow path:
  - simple answer path
  - code-edit path
  - investigate-and-fix path
  - research-first path
- Build minimal ordered plan with completion criteria.
- Prefer deterministic routing and typed action contracts.

Output: `execution_plan` with step list and stop conditions.

## Stage C — Context Retrieval (Local-First)

Retrieval order:

1. Workspace context (open files, related symbols, tests, docs)
2. Project memory and prior successful fixes
3. Existing playbooks/runbooks

Rules:

- Read before edit.
- Use narrow, high-signal context first.
- Track why each context item was selected.

Output: `evidence_bundle_local`.

## Stage D — Knowledge Gap Detection

Determine whether local context is enough.

Trigger external research when any of these are true:

- Confidence below threshold (e.g., `< 0.65`).
- User asks for latest external facts (API changes, versions, policies, release behavior).
- Error references unknown third-party behavior.
- Local docs do not answer the key question.

Output: `needs_external_research = true|false` with reason.

## Stage E — External Research (Web Fallback)

When `needs_external_research = true`:

- Query authoritative sources first (official docs, standards, primary project sources).
- Prefer recent, version-matching documentation.
- Fetch multiple sources for cross-checking when impact is high.
- Extract only task-relevant facts, then merge with local context.

Research quality controls:

- Mark stale/uncertain facts explicitly.
- Never invent external details.
- Record sources used in internal trace/audit.

Output: `evidence_bundle_external` + `confidence_update`.

## Stage F — Reasoning & Decision Layer

- Synthesize local + external evidence.
- Generate 1–3 candidate approaches.
- Score candidates by:
  - correctness likelihood
  - safety/risk
  - implementation effort
  - reversibility
- Select best option and preserve alternatives for fallback.

Output: `chosen_strategy` with rationale and assumptions.

## Stage G — Action Execution

Possible actions:

- answer only
- propose patch
- edit files
- run tests/build/lint
- collect diagnostics

Execution principles:

- Minimal surgical changes.
- Keep style consistent with existing code.
- Avoid unrelated modifications.
- Log important action boundaries.

Output: code changes + execution artifacts.

## Stage H — Verification & Self-Check

- Run most targeted verification first, then broader checks.
- If failure:
  - parse failure category
  - attempt bounded repair loop
  - stop with blocker summary if unresolved

Output: `verification_result` + repair trace (if any).

## Stage I — Response Composition

Response should include:

- what was done
- where it changed
- validation result
- known limits/assumptions
- clear next step

If unresolved, return:

- blocker reason
- what was tried
- best next action for user/agent

---

## 3) Thinking + Reasoning Policy

`aicode` should apply these reasoning standards per request:

- **Constraint-first thinking:** identify non-negotiables before proposing steps.
- **Evidence-backed claims:** tie conclusions to retrieved context.
- **Uncertainty-aware output:** explicitly say when confidence is low.
- **Safety-first execution:** prefer reversible, testable actions.
- **Iteration over guessing:** when uncertain, retrieve/verify instead of hallucinating.

---

## 4) Web Research Policy (Required Capability)

If the answer is unknown or likely outdated, `aicode` must research before finalizing.

Minimum policy:

- Search web when confidence is below threshold.
- Prioritize official documentation and primary sources.
- Capture source URL + short fact summary in trace.
- Use version/date-aware interpretation.
- Fall back to “best effort + uncertainty” when authoritative source is unavailable.

Do not:

- fabricate references
- present guessed facts as certain
- skip research when user explicitly asked for latest info

---

## 5) Capability Inventory (Copilot-Like Surface)

This is the target capability set `aicode` should expose consistently:

### A. Prompt Understanding
- Intent classification
- Entity extraction (files, symbols, frameworks)
- Ambiguity detection + clarifying question strategy

### B. Context & Retrieval
- Symbol/file/test retrieval
- Semantic search + context packing
- Project memory retrieval
- Prior-fix retrieval

### C. Research
- External documentation retrieval
- Multi-source validation for high-risk changes
- Freshness/version checks

### D. Reasoning & Planning
- Multi-step plan generation
- Tradeoff analysis
- Risk estimation
- Tool selection strategy

### E. Code Execution
- Code generation/refactor/edit
- Patch application
- Multi-file awareness
- Rollback safety

### F. Validation
- Targeted test selection
- Build/lint/type checks
- Failure parsing + bounded autofix loop

### G. Communication UX
- Progress updates during long work
- Clear summaries of changes
- Actionable next steps
- Transparent uncertainty reporting

### H. Learning
- Learn explicit user preferences
- Apply learned preferences by intent
- Accept corrections and update behavior

### I. Governance & Safety
- Approval policies
- Audit traces
- command guard / policy checks
- retention/privacy controls

### J. Repository-Wide Consistency
- Same decision logic across CLI/API/extension
- Shared trace semantics for routing/research/verification/learning
- Acceptance criteria aligned to Main Baseline v1

---

## 6) Decision Matrix: When to Answer vs Research vs Ask

### Answer directly

- Local context is sufficient
- High confidence
- No dependency on external freshness

### Research first

- External facts likely changed
- User asks for latest/official guidance
- Error involves unknown third-party behavior

### Ask clarifying question

- Prompt intent is ambiguous
- Multiple materially different interpretations
- Missing constraints affect implementation direction

---

## 7) Quality Bar for “Strong Response”

A response is strong when it is:

- correct enough to execute confidently
- scoped to the user’s ask
- verified where code is changed
- transparent about uncertainty
- concise and actionable

Anti-patterns to avoid:

- generic advice without repo context
- overconfident guessing
- big unverified edits
- ignoring user constraints

---

## 8) Implementation Backlog (Execution Order)

### Phase 1 — Reasoning Core

1. Add confidence scoring at intent and answer stages.
2. Add explicit `needs_external_research` decision output.
3. Add strategy selection with rationale object.

### Phase 2 — Research Integration

1. Add web retrieval tool path in chat engine workflow.
2. Add source ranking (official docs first).
3. Add citation metadata in internal trace logs.

### Phase 3 — Robust Execution

1. Strengthen fallback behavior for unknowns and failed tools.
2. Add bounded retry for retrieval failures.
3. Improve failure-to-repair routing.

### Phase 4 — Evaluation & Learning

1. Add benchmark prompts for reasoning/research quality.
2. Add metrics: research trigger precision, factual correction rate, time-to-correct-answer.
3. Use feedback/corrections to tune thresholds and routing.

---

## 9) Metrics to Track Weekly

- Prompt understanding accuracy
- Correct tool/routing selection rate
- Research trigger precision/recall
- Answer factuality (manual sample checks)
- First-pass success rate
- Repair loop success rate
- User correction rate per 100 prompts
- Mean time to useful answer

---

## 10) Definition of Done (Copilot-Like vNext)

`aicode` reaches this milestone when:

1. It reliably identifies when it does not know enough.
2. It performs web research for unknown/outdated topics before finalizing.
3. It produces evidence-backed, concise responses with transparent uncertainty.
4. It executes code tasks safely with verification and bounded repair loops.
5. It improves over time from user teaching and correction signals.

---

## 11) Immediate Next Build Steps (Today+)

1. Implement silent-exception observability hardening (P0 item 2).
2. Add confidence + research-trigger fields to request/response traces.
3. Wire a research-first branch in chat flow for low-confidence unknowns.
4. Add tests for: unknown prompt -> research path -> grounded response.
