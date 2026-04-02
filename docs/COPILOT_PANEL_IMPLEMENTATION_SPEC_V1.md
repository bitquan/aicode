# Copilot-Ready Implementation Spec — Composer-First Panel

Date: 2026-04-02  
Scope: VS Code panel first, then CLI/TUI parity.  
Primary change: make the composer + current task card the main product surface; push everything else into progressive disclosure.

---

## 0) Current baseline (mapped to code)

- Panel UI is currently monolithic inside `vscode-extension/src/extension.ts` in `panelHtml()`.
- Streaming state is already available through webview messages:
  - `streamStart`, `streamRoute`, `streamDelta`, `streamDone`, `error`, `actionLog`, `serverStatus`.
- Backend already provides key metadata needed for task-first cards:
  - `src/app_service.py`: `next_step`, `events`, `route_attempts`, research flags.
  - `src/server.py`: SSE events for route/status/event/result/delta/done.
- TUI currently uses command handlers in `src/ui/terminal_ui.py` and does not yet mirror panel task framing.

---

## 1) Information architecture target

## Top bar (always visible)

- Runtime pill + one primary action.
- Move all runtime controls under one collapsed runtime menu.

## Middle (always visible)

- Large composer (visual center).
- Current task status card (single active run).
- Compact 4-stage strip: `Intent → Plan → Execute → Verify`.

## Lower (collapsed by default)

- History
- Diagnostics
- Runtime details

## Right rail (tabbed)

- Tabs: `Chat | Tools | Diagnostics | Todos`
- Only active tab content visible.

---

## 2) Interaction model target

Every request must resolve to one consistent shape:

1. Intent understood
2. Plan selected
3. Progress visible
4. Outcome + next step

Rules:

- One dominant action per area.
- One next-step hint per task card.
- Failures branch to explicit recovery actions.

---

## 3) Data contract (panel-facing)

Use existing payload fields first; add only minimal derived fields client-side.

## Existing server fields to use (no backend break required)

- `action`, `confidence`, `response`, `next_step`
- `events[]` (`kind`, `message`)
- `route_attempts[]`
- `needs_external_research`, `research_trigger_reason`
- `output_trace_id`, `run_id`, `state`, `verification_plan`

## Client-side derived fields in webview script

Add a normalized task view-model in `panelHtml()` script:

- `taskId`
- `command`
- `intentLabel` (from first route)
- `planLabel` (from route_attempts or first planner/research event)
- `stage` (`intent|plan|execute|verify|done|failed`)
- `activity[]` (task-scoped events)
- `failure` (`message`, `kind`, `traceId?`)
- `nextStep`

---

## 4) File-by-file implementation plan

## A. VS Code panel (P0/P1)

### File: `vscode-extension/src/extension.ts`

#### A1. Restructure `panelHtml()` into explicit render sections

Keep in same file initially; create helper blocks/functions in template script:

- `renderTopBar()`
- `renderComposer()`
- `renderCurrentTaskCard()`
- `renderProgressStrip(stageState)`
- `renderTaskActivityLog(task)`
- `renderFailureBranches(task)`
- `renderRightRailTabs(activeTab)`
- `renderCollapsedSections()`

#### A2. Collapse runtime controls

- Replace separate top-level buttons with one `Runtime` menu control.
- Keep existing message types (`health`, `startServer`, `restartServer`, `stopServer`, `runWorkspaceTask`).

#### A3. Composer-first focus

- Increase composer area prominence.
- Keep existing quick actions: `editCurrentFile`, `editSelection`, `inlineChat`.
- Keep command retry chips, but visually secondary.

#### A4. Convert current task to status card

- Replace current freeform `entry` with structured card blocks:
  - header (intent/action + confidence + status)
  - progress strip
  - response body
  - one `next step`
  - primary action cluster (`Retry`, `Clarify`, conditional `Apply`)

#### A5. Task-scoped activity log

- Stop rendering `#actionLog` as global-only primary diagnostic surface.
- Attach streamed `event/status/route` entries to active task `activity[]`.
- Keep global `ActionLogStore` for extension observability, but move UI exposure behind collapsed diagnostics.

#### A6. Failure branching card

- On `error` or failure-like completion, render branch actions:
  - `Retry same path`
  - `Switch to research`
  - `Clarify request`
  - `Open diagnostics`
- Map branch buttons to existing post messages:
  - Retry => `ask` with original command
  - Switch to research => `ask` with `research: <original command>` (or equivalent directive)
  - Clarify => `ask` with clarify prompt
  - Open diagnostics => expand diagnostics section

#### A7. Right-rail tabs

- Add tab state in webview script (`activeRightRailTab`).
- Start with light content wrappers around existing content blocks; avoid backend changes.

#### A8. Keep theme safety constraints

- Use only `--vscode-*` CSS vars.
- Do not add icon dependency or external CSS framework.

---

## B. App/service normalization (P0/P1)

### File: `src/app_service.py`

#### B1. Preserve single canonical next step

- Keep `_canonical_next_step()` as source of truth.
- Ensure failure responses still emit one concise next-step sentence.

#### B2. Ensure event shape consistency

- Continue returning ordered `events` with clear `kind` values.
- Keep `route_attempts` complete for progress strip derivation.

### File: `src/server.py`

#### B3. Keep SSE event completeness

- Ensure stream path continues sending: `route`, `status`, `event`, `result`, `delta`, `done`, `error`.
- Include any needed metadata in `done` payload for failure branch rendering (without breaking existing fields).

---

## C. CLI/TUI parity (P1)

### File: `src/ui/terminal_ui.py`

#### C1. Add task-shaped rendering helpers

- `print_intent(...)`
- `print_plan(...)`
- `print_progress(...)`
- `print_outcome(...)`
- `print_next_step(...)`

#### C2. Align failure recovery options

- For failed workflows, print 2–3 actionable branch options mirroring panel labels.

### File: `src/main.py`

#### C3. Keep command entrypoints unchanged; adjust displayed framing only.

---

## 5) Build order (execution sequence)

Use this exact order for implementation PRs:

1. Collapse runtime controls into one menu (`extension.ts`)
2. Enlarge and center composer (`extension.ts`)
3. Convert current task into status card (`extension.ts`)
4. Add 4-stage progress strip (`extension.ts` using existing stream/app metadata)
5. Create task-scoped activity logs (`extension.ts` + reuse `events`)
6. Add branching failure cards (`extension.ts` + minimal `app_service.py` polish)
7. Finish right-rail tabs (`extension.ts`)
8. Mirror structure in CLI/TUI (`terminal_ui.py`, optionally tiny helpers in `main.py`)

---

## 6) Suggested PR slices (Copilot task units)

## PR-1: Panel IA shell + runtime menu

- Files: `vscode-extension/src/extension.ts`
- Output: top/middle/lower zones; runtime details collapsed behind one trigger.

## PR-2: Composer-first + structured current task card

- Files: `vscode-extension/src/extension.ts`
- Output: large composer, status-card framing, one dominant actions row.

## PR-3: Progress strip + task-scoped activity

- Files: `vscode-extension/src/extension.ts`
- Output: stage strip + per-task event timeline.

## PR-4: Failure branching

- Files: `vscode-extension/src/extension.ts`, `src/app_service.py` (only if needed for hint/event consistency)
- Output: branch card with retry/research/clarify/diagnostics actions.

## PR-5: Right rail tabs + cleanup

- Files: `vscode-extension/src/extension.ts`
- Output: `Chat/Tools/Diagnostics/Todos` tabs replacing dense single wall.

## PR-6: CLI/TUI parity

- Files: `src/ui/terminal_ui.py`, optional `src/main.py`
- Output: Intent→Plan→Progress→Outcome shape in terminal UX.

---

## 7) Test and validation mapping

## Existing tests to keep green

- `vscode-extension/smoke/panel-flow.test.cjs`
- `vscode-extension/smoke/runtime-support.test.cjs`
- `tests/test_app_service.py`
- `tests/test_server.py`
- `tests/test_server_app_command.py`

## New/updated assertions to add during implementation

- Panel smoke:
  - current task card renders stage strip after stream events
  - exactly one next-step hint visible per completed card
  - failure branch actions render on error path
- App/service:
  - `next_step` always non-empty
  - `route_attempts` and `events` order remains stable

---

## 8) Acceptance criteria

- User sees runtime state + single primary top action at a glance.
- Composer and current task card are visually dominant without opening lower sections.
- Each request shows Intent/Plan/Execute/Verify progression.
- Diagnostics/history/runtime are discoverable but collapsed by default.
- Failure states always provide 2–4 explicit recovery options.
- No added external UI dependencies; all colors/tokens remain `--vscode-*` based.
- Streaming/task-card model remains intact.

---

## 9) Non-goals for this cycle

- No new icon library.
- No React migration or new bundler.
- No replacement of server protocol.
- No extra pages/modals/animations beyond described behavior.
