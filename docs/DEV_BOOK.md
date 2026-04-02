# Developer Book

## Purpose

This is the practical engineering guide for `coding-ai-app`.

Use it to understand:

- what the product is trying to become
- how the repo is layered
- where new behavior should live
- how to keep the project clean while pushing toward Codex/Copilot parity

## Product Truth

`coding-ai-app` is a local-first AI developer assistant. It is not just a prompt wrapper and it is not just a VS Code panel.

The product surface is shared across:

- CLI
- local API server
- shared app service
- chat/routing engine
- VS Code extension
- self-improvement and readiness systems

The long-term goal is parity with strong AI coding assistants, but the repo should stay honest about what is already production-worthy versus what is still baseline or experimental.

## Repo Layer Map

### 1. Entry Surfaces

- `src/main.py`
- `src/server.py`
- `src/app_service.py`
- `vscode-extension/src/extension.ts`

These files should stay focused on transport, UX, and orchestration boundaries.

### 2. Shared Command and Routing Layer

- `src/tools/commanding/models.py`
- `src/tools/commanding/request_parser.py`
- `src/tools/commanding/dispatcher.py`
- `src/tools/commanding/handlers/`

This is the main contract layer. If a behavior is supposed to work across surfaces, it should be expressed here instead of being duplicated.

### 3. Domain Logic

- `src/tools/`

This is where verification, learning, readiness, research, governance, repair, and self-improvement behavior should live.

### 4. Runtime and Product Integrity

- `src/config/runtime_manifest.json`
- `src/config/readiness_canaries.json`
- `vscode-extension/src/runtime_support.ts`
- `vscode-extension/scripts/`

These files protect against stale installs, runtime mismatch, and silent drift between packaged and loaded artifacts.

### 5. Tests and Docs

- `tests/`
- `docs/`

Behavior is not finished until tests and docs tell the same story.

## Architecture Rules

1. Keep entry surfaces thin.
2. Prefer shared typed routing over special-case glue.
3. Keep heavy status and benchmark work explicit.
4. Use repo research before applying feature changes.
5. Preserve rollback and verification behavior.
6. Keep UI state honest about runtime truth.

## What "Parity" Means Here

Parity with Codex/Copilot does not mean copying someone else's product. It means this repo can reliably do the work a serious AI dev assistant should do:

- understand requests
- research the repo first
- identify the right files
- propose or apply minimal edits
- run the right checks
- recover from failures
- explain its limits honestly
- maintain a usable IDE workflow

Current truthful status:

- strong shared routing foundation: yes
- self-improvement under supervision: yes
- safe apply/verify/rollback loop: yes
- packaged VS Code runtime integrity: yes
- true autonomous multi-agent execution: not yet

## Default Development Loop

### Local runtime

1. Start Ollama.
2. Start the local server.
3. Use the VS Code extension or CLI against the same backend.

### High-signal checks

- `./.venv/bin/python -m pytest -q`
- `npm --prefix vscode-extension run compile:clean`
- `npm --prefix vscode-extension run test:smoke`
- `npm --prefix vscode-extension run verify:vsix`

### When changing only one surface

Use the smallest matching verification set first. Expand to the full suite when shared contracts or runtime behavior change.

## Docs Sync Contract

Keep these docs aligned:

- `README.md`: operator-facing start and run guidance
- `ROADMAP.md`: status, direction, and proof log
- `docs/COMMAND_BOOK.md`: commands, tasks, endpoints
- `docs/MAINTAINER_PLAYBOOK.md`: release and maintenance workflow
- `docs/HANDOFF_GUIDE.md`: transfer of context
- `docs/COPILOT_LIKE_FLOW_BLUEPRINT.md`: behavior target
- `docs/SELF_IMPROVEMENT_BASELINE_PACK_V1.md`: gated self-improvement rules

If a change affects runtime truth, commands, parity claims, release flow, or onboarding, update the relevant docs before calling the work done.

## Clean Tree Rules

- Do not mix unrelated changes.
- Do not commit generated artifacts unless they are intentional packaged outputs.
- Keep runtime state and learning stores untracked unless there is a specific reason otherwise.
- Prefer focused commits that can be understood without replaying the whole session.

## Where to Put New Work

### Add a new cross-surface action

Start in:

- `src/tools/commanding/models.py`
- `src/tools/commanding/request_parser.py`
- `src/tools/commanding/dispatcher.py`
- a matching handler under `src/tools/commanding/handlers/`

Then wire the UI surfaces to that shared action.

### Add a new VS Code UX capability

Start in:

- `vscode-extension/src/extension.ts`
- `vscode-extension/src/runtime_support.ts`

But prefer reusing backend behavior instead of inventing extension-only business logic.

### Add a new self-improvement or learning behavior

Start in:

- `src/tools/self_improve.py`
- `src/tools/live_mode.py`
- `src/tools/decision_timeline.py`
- `src/tools/readiness_suite.py`

Then prove it with tests and update the baseline docs if the capability boundary changed.

## What To Avoid

- parallel logic paths that drift between CLI, API, and extension
- vague status text that hides runtime truth
- heavy validation hidden inside "status" or startup paths
- one giant docs update that never gets linked from the repo entrypoints

## First Files to Read

If you are new to the repo, start here:

1. `README.md`
2. `ROADMAP.md`
3. `docs/SELF_IMPROVEMENT_BASELINE_PACK_V1.md`
4. `src/app_service.py`
5. `src/tools/commanding/request_parser.py`
6. `vscode-extension/src/extension.ts`
