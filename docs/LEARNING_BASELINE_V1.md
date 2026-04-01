# Learning Baseline v1 (Copilot-like for this Repo)

## Goal

Establish a practical baseline that makes this project behave like a strong coding copilot for this repository, then continuously improve from user prompts and feedback.

Scope includes:
- Local app/API/extension workflows in this repo
- Deterministic routing + tool usage + memory application
- Learn-and-adapt loop from explicit user teaching and corrections

Out of scope:
- Proprietary cloud internals from external products
- External telemetry/ranking systems not implemented in this codebase

---

## 1) Capability Matrix (Baseline)

### A. Conversation & Intent

- Greeting / capability summary
- Repo understanding queries ("what can you tell me about this repo")
- Task intent routing:
  - generate
  - edit / autofix
  - review / debug / profile / coverage
  - architecture / schema / diff visualization
  - team/audit/rbac/analytics
- Ambiguity handling: ask follow-up when intent confidence is low

### B. Coding Execution

- Generate code with evaluation
- Edit with instruction + patch flow
- Autofix with retry strategy and rollback
- Test execution and summary
- Search/index/browse workspace context

### C. Learning & Memory

- Explicit teaching prompts:
  - learn:
  - teach:
  - remember this
  - note:
- Persist lessons in project memory + team knowledge base
- Apply learned preferences in relevant tasks (generate/autofix)
- Support correction prompts to update/override old preferences

### D. Team & Governance

- Shared team knowledge recall
- Audit trail visibility
- RBAC checks
- Cost and analytics snapshots

### E. Extension UX Baseline

- Ask command
- Status check command
- Chat panel
- Panel history + retry
- In-panel API health check + URL-aware errors

---

## 2) Learning Data Schema (Baseline)

### Prompt Event

- id: string (trace id)
- timestamp: ISO datetime
- source: cli | api | extension
- raw_prompt: string
- normalized_prompt: string
- intent: string
- confidence: float
- action_taken: string
- result_status: success | partial | failure

### Learned Preference

- preference_id: string
- timestamp: ISO datetime
- user_scope: global | project | session
- category: style | testing | safety | tooling | output_format | workflow
- statement: string
- origin_prompt: string
- confidence: float
- active: bool
- supersedes: preference_id | null

### Correction Event

- correction_id: string
- timestamp: ISO datetime
- target_preference_id: string | null
- correction_type: replace | disable | strengthen
- correction_text: string
- applied: bool

### Retrieval Context

- request_intent: string
- selected_preferences: list[preference_id]
- retrieval_reason: string per preference

### Output Trace

- output_id: string
- prompt_event_id: string
- applied_preferences: list[preference_id]
- tools_used: list[string]
- eval_summary: string

---

## 3) Evaluation Checklist (Baseline Acceptance)

### Intent & Routing

- Greeting/capability prompts never route to code generation
- Repo-understanding prompts route to repo-summary action
- Misroute rate for top 20 prompt types under 10%

### Learning Behavior

- Explicit teaching prompt persists lesson
- Next relevant generate/autofix call includes learned preference block
- Correction prompt updates preference behavior within next request
- Duplicate lessons are deduplicated in retrieval

### Execution Quality

- No crash on empty/short prompts
- No blocking startup due to heavy context preloads
- API endpoint /v1/aicode/command responds under 2s for simple prompts (status/help)

### UX & Operability

- Extension panel can check API health in one click
- Error surfaces include request URL
- History + retry works for repeated prompts

### Safety & Consistency

- Preference application is scoped (not blindly applied to unrelated intents)
- Conflicting preferences resolve by recency + explicit correction
- Audit trail includes learning and correction actions

---

## 4) Implementation Order (4-Week Baseline)

### Week 1 — Routing Baseline

1. Add prompt taxonomy map for top 20 intents
2. Add dedicated repo-understanding action and handler
3. Add fallback clarification question flow for low-confidence parsing
4. Add routing regression tests by intent bucket

### Week 2 — Learning Core

1. Finalize learned-preference schema + storage utilities
2. Add correction-update pipeline (replace/disable/strengthen)
3. Add scoped retrieval (intent-aware top-k preferences)
4. Add tests for persistence, retrieval, correction, dedupe

### Week 3 — Quality + Transparency

1. Add applied-preference trace in responses/logs
2. Add evaluation harness for baseline prompts
3. Add metrics: routing accuracy, preference hit rate, correction success rate
4. Add startup performance checks for API path

### Week 4 — Productization Baseline

1. Add extension controls for “show applied preferences” and “clear learned preference”
2. Add export/import for learned preferences
3. Add docs and operator playbook for maintaining learning quality
4. Freeze Baseline v1 and open Baseline v1.1 backlog

---

## Definition of Done (Baseline v1)

- Capability matrix fully implemented for baseline intents
- Learning loop works end-to-end (teach -> persist -> apply -> correct)
- Acceptance checklist passes in CI
- Extension panel supports reliable operational debugging
- Team can run and evaluate baseline with repeatable scripts
