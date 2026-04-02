# UI/UX Redesign Plan v1

Date: 2026-04-02  
Scope: VS Code extension first, then CLI/TUI parity.

Implementation companion: `docs/COPILOT_PANEL_IMPLEMENTATION_SPEC_V1.md`

---

## Goal

Make `aicode` feel clear, calm, and task-first:

- users should always know **where they are**,
- what `aicode` is **currently doing**,
- and the **next best action** without guessing.

---

## Current UX Gaps (Observed)

1. **Panel overload**
   - One screen mixes chat, controls, health, action log, and command history.
   - Cognitive load is high for first-time and repeated usage.

2. **Weak information hierarchy**
   - Route/progress/confidence/status are shown, but not prioritized consistently.
   - Important outcomes and next actions get buried in streaming text.

3. **Inconsistent interaction model**
   - Similar workflows appear differently across panel, status bar, and CLI.
   - “Ask”, “edit current file”, “inline chat”, and “health” feel separate instead of one flow.

4. **Low trust signaling during long actions**
   - Users see deltas/stream output, but not a stable task-state timeline.
   - Recovery paths exist, but UX does not foreground them.

5. **Action log utility is low**
   - Logs are detailed but not task-grouped (hard to scan by request).

---

## UX North-Star

Every request should read as a simple 4-step frame:

1. **Intent understood** (what we think you asked)
2. **Plan selected** (what we will do next)
3. **Progress visible** (live stage + key events)
4. **Outcome + next step** (result + one-click follow-up)

---

## Redesign Principles

- **Task-first, tool-second**: start from user goal, not controls.
- **One primary action per screen area**: reduce competing buttons.
- **Progressive disclosure**: hide advanced diagnostics until expanded.
- **Stable status language**: same wording in panel, status bar, and CLI.
- **Recoverability by default**: show retry/clarify/fallback paths inline.

---

## Implementation Plan

## Phase 1 — Information Architecture (P0)

### Deliverables

- Reframe panel into 3 zones:
  1. **Composer** (ask/edit prompt)
  2. **Current Task Card** (route, stage, confidence, status)
  3. **History** (collapsible previous tasks)
- Move health + runtime details into compact “Runtime” pill + expandable details.
- Keep action log collapsed by default under each task.

### Files

- `vscode-extension/src/extension.ts`
  - split `panelHtml()` into composable render blocks
  - task-card message model (`streamStart`, `streamRoute`, `streamDelta`, `streamDone`, `error`)
- `vscode-extension/src/runtime_support.ts`
  - standardize runtime summary labels used by panel + status bar

### Acceptance

- First-time user can run one request without using any secondary control.
- Runtime health visible at a glance without occupying primary panel space.

---

## Phase 2 — Interaction Model Unification (P0)

### Deliverables

- Introduce **quick actions bound to current context**:
  - `Retry`
  - `Clarify`
  - `Apply suggested edit` (when applicable)
- Normalize server response display:
  - top-line summary
  - expandable details/events
  - explicit next recommended action

### Files

- `vscode-extension/src/extension.ts`
  - unify response rendering path for stream and non-stream
- `src/app_service.py`
  - ensure response metadata always includes one canonical “next step” hint
- `src/tools/commanding/handlers/*.py`
  - harmonize final sentence pattern: “If you want, I can … next.”

### Acceptance

- Stream and non-stream responses produce the same final card structure.
- Each completed request shows exactly one recommended next action.

---

## Phase 3 — Trust + Debuggability UX (P1)

### Deliverables

- Add compact “Request Timeline” in each task card:
  - routed
  - researched (if any)
  - executed
  - verified
- Add failure cards with explicit branch choices:
  - retry
  - switch to research
  - ask for clarification

### Files

- `vscode-extension/src/extension.ts`
- `src/app_service.py` (events normalization)
- `src/tools/learning_events.py` (event trace consistency)

### Acceptance

- On failure, user sees actionable options without reading raw logs.
- Timeline corresponds to backend event sequence.

---

## Phase 4 — CLI/TUI Parity (P1)

### Deliverables

- Mirror panel response shape in CLI/TUI:
  - summary
  - progress/state
  - next step
- Reduce command sprawl in TUI help into grouped commands:
  - Ask
  - Edit
  - Diagnose
  - Learn

### Files

- `src/main.py`
- `src/ui/terminal_ui.py`
- `src/tools/chat_engine.py` (shared phrasing helpers if needed)

### Acceptance

- Same request yields structurally similar response in extension and CLI.
- TUI help is scannable in under 10 seconds.

---

## Delivery Order (Recommended)

1. Phase 1 panel IA split
2. Phase 2 interaction unification
3. Phase 3 trust timeline/failure cards
4. Phase 4 CLI/TUI parity

---

## Metrics (UX Success)

Track weekly:

- Time to first successful command in panel
- Retry rate per 100 commands
- Clarification rate after first answer
- Stream completion rate
- “Next action used” rate
- Help-summary usage after failed request

---

## Test Plan

Add/extend tests for:

- Panel rendering state transitions (`ready → route → delta → done/error`)
- Response card format invariants
- Presence of single next-action hint
- Runtime summary consistency

Target files:

- `vscode-extension/smoke/*.test.cjs`
- `tests/test_layer3_chat_features.py`
- `tests/test_chat_help_summary.py`

---

## Definition of Done (UI/UX v1)

Done when:

1. Panel has clear task hierarchy and reduced control clutter.
2. Streaming and non-streaming output share one response model.
3. Every response includes explicit next step and consistent language.
4. Failure states present guided recovery choices.
5. CLI/TUI mirror the same outcome framing.
