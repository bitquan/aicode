# Main Baseline v1 (Repo-Wide, Copilot-Like)

## Goal

Define a single **Main Baseline v1** for this repository that follows the Copilot-like flow and covers all major surfaces: CLI, chat engine, API server, VS Code extension, tools, tests, governance, and learning.

This baseline is the primary execution contract for `aicode`.

Status: Implemented in the repository as of 2026-04-02.

Primary implementation evidence:

- Acceptance gate: `tests/test_learning_baseline_v1.py`
- Self-improvement promotion gate: `docs/SELF_IMPROVEMENT_BASELINE_PACK_V1.md`
- Prompt telemetry: `.autofix_reports/prompt_events.jsonl`
- Retrieval/research trace: `.autofix_reports/retrieval_traces.jsonl`
- Output trace: `.autofix_reports/output_traces.jsonl`
- Learning/correction metrics: `src/tools/learning_metrics.py`

Companion flow spec: `docs/COPILOT_LIKE_FLOW_BLUEPRINT.md`

---

## 1) Baseline Scope (Whole Repo)

Baseline v1 applies to:

- `src/main.py` (CLI + command entrypoints)
- `src/tools/chat_engine.py` (prompt intake, routing, execution)
- `src/server.py` + app service flow (API behavior)
- `vscode-extension/` (editor workflow parity)
- `src/tools/*` specialized capabilities (edit/fix/review/research/ops)
- `tests/` acceptance and regression quality
- docs + playbooks + roadmap artifacts in `docs/`

Out of scope:

- Proprietary external internals from other products
- Unsupported deployment targets not represented in this repo

---

## 2) Core Operating Flow (Must Follow)

Every request should follow this flow:

1. Prompt intake + normalization
2. Intent routing + plan
3. Local retrieval (repo-first)
4. Knowledge-gap detection
5. External research fallback (when needed)
6. Reasoning + strategy selection
7. Execution (answer/edit/run tools)
8. Verification + repair loop
9. Response + trace transparency

Source of detailed stage behavior: `docs/COPILOT_LIKE_FLOW_BLUEPRINT.md`.

---

## 3) Capability Matrix (Main Baseline v1)

### A. Prompt Understanding + Routing

- Classify user intent reliably (question/edit/fix/review/research/ops)
- Detect ambiguity and request clarification when confidence is low
- Route to deterministic action contracts

### B. Repo Context + Retrieval

- File/symbol/test discovery
- Semantic retrieval and context packing
- Read-first policy before edits
- Use project memory and prior successful fix memory

### C. Reasoning + Planning

- Generate minimal step plan with completion criteria
- Compare candidate approaches and pick safest effective option
- Record assumptions and uncertainty

### D. Research (External Fallback)

- Trigger web research when local evidence is insufficient or stale
- Prefer official sources and version-matching docs
- Capture source summary in trace when research is used

### E. Code & Tool Execution

- Generate/edit/refactor with minimal diffs
- Run appropriate tools and commands safely
- Respect workspace boundaries and policy constraints

### F. Verification + Repair

- Run targeted tests first, then broader checks when needed
- Parse failures and run bounded repair loops
- Stop with blocker report if unresolved

### G. Communication UX

- Clear progress updates during longer work
- Concise final summary with what changed and validation status
- Explicit uncertainty and next steps

### H. Learning (Folded Into Main Baseline)

- Accept explicit teaching prompts (`learn`, `teach`, `remember`, `note`)
- Persist lessons in project/team memory stores
- Apply relevant lessons by intent and context
- Support correction flow (replace/disable/strengthen)
- Show which lessons/preferences were applied in trace

### I. Governance + Ops

- Approval and role-aware policy checks
- Audit trail coverage for key actions
- Budget/telemetry/compliance hooks remain available

---

## 4) Baseline Data Contracts

## Prompt Event

- id
- timestamp
- source (`cli|api|extension`)
- raw_prompt
- normalized_prompt
- intent
- confidence
- needs_external_research
- action_taken
- result_status (`success|partial|failure`)

## Learning Records

- preference_id
- scope (`global|project|session`)
- category
- statement
- confidence
- active
- supersedes

## Correction Event

- correction_id
- target_preference_id
- correction_type (`replace|disable|strengthen`)
- correction_text
- applied

## Retrieval/Research Trace

- request_intent
- local_context_selected
- research_trigger_reason
- selected_sources (when research used)
- selected_preferences

## Output Trace

- output_id
- prompt_event_id
- tools_used
- applied_preferences
- verification_summary

---

## 5) Baseline Acceptance Checklist

## Intent + Routing

- Greeting/help prompts do not misroute to heavy code actions
- Repo-summary prompts route correctly
- Low-confidence prompts produce clarification or research path

## Research + Reasoning

- Unknown/outdated questions trigger research-first branch
- Responses avoid fabricated external facts
- Uncertainty is explicit when evidence is partial

## Execution Quality

- No crash on empty/short prompts
- Edits remain scoped and reversible
- Verification runs for code-changing tasks

## Learning Behavior

- Teaching prompt persists lesson
- Next relevant request applies lesson
- Correction updates behavior quickly
- Duplicate lessons are deduplicated in retrieval

## UX + Operability

- API simple commands are responsive
- Extension can run core ask/status workflows
- Errors include actionable context

## Safety + Governance

- Policy checks enforced where required
- Audit trail includes learning/research/execution actions

---

## 6) Implementation Order (Baseline v1)

### Phase 1 — Routing + Confidence

1. Normalize intent taxonomy for top workflows
2. Add confidence scoring and low-confidence handling
3. Add explicit `needs_external_research` decision field

### Phase 2 — Research Path

1. Wire research-first branch into chat engine pipeline
2. Add source prioritization (official docs first)
3. Add research trace metadata in logs

### Phase 3 — Learning Integration

1. Ensure teach -> persist -> retrieve -> apply loop is deterministic
2. Ensure correction pipeline updates active preferences
3. Add preference-application visibility in responses/traces

### Phase 4 — Validation + Productization

1. Add benchmark prompts for reasoning/research quality
2. Add metrics dashboards for routing/research/learning outcomes
3. Lock CI acceptance gates for baseline checklist

---

## 7) Weekly Metrics

- Routing accuracy
- Research trigger precision/recall
- Factual correction rate after research
- First-pass task success rate
- Repair-loop success rate
- Preference hit rate on relevant requests
- User correction rate per 100 prompts
- Mean time to useful answer

---

## Definition of Done (Main Baseline v1)

Baseline v1 is complete when:

1. Copilot-like flow is consistently followed across CLI/API/extension paths.
2. `aicode` reliably detects unknowns and triggers research when needed.
3. Learning loop works end-to-end (teach -> apply -> correct).
4. Code tasks are verified with safe, bounded repair behavior.
5. Acceptance checklist is automated and passing in CI.
