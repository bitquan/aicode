# GitHub Copilot Instructions for `coding-ai-app`

## Mission

Help this repo become a trustworthy local AI developer assistant with honest, test-backed progress toward Codex/Copilot parity.

Do not optimize for flashy output. Optimize for:

- repo-first research
- small safe diffs
- layered architecture
- docs that stay in sync
- clean commits
- strong verification

## What This Project Is

`coding-ai-app` is a local-first coding assistant backed by Ollama. The same action system should work across:

- CLI
- local FastAPI server
- shared app service
- chat/routing engine
- VS Code extension
- self-improvement and readiness tooling

The product goal is not "another chat panel." The goal is a local AI dev assistant that can research, edit, verify, roll back, learn, and hand work off cleanly.

## Architecture Map

Treat these as the main repo surfaces:

- `src/main.py`: CLI and terminal entry surface
- `src/server.py`: local API and health/readiness endpoints
- `src/app_service.py`: shared app-facing orchestration
- `src/tools/commanding/`: typed request parsing, dispatch, and handler routing
- `src/tools/`: domain logic, learning, readiness, governance, and repair systems
- `vscode-extension/src/extension.ts`: VS Code UX surface
- `vscode-extension/src/runtime_support.ts`: extension runtime/build integrity helpers
- `tests/`: behavior and regression coverage
- `docs/`: operational truth, parity goals, and handoff material

## Layering Rules

Keep the repo structured in layers:

1. Entry surfaces stay thin.
2. Routing stays shared and typed.
3. Domain behavior lives in tool modules, not in UI glue.
4. VS Code UI should call shared backend behavior, not invent a parallel product.
5. Docs and tests must move with behavior changes.

Do not add new one-off flows to just one surface if the behavior should exist across CLI, API, chat, and extension.

## Default Working Style

When helping in this repo:

1. Research the repo first.
2. Identify likely files and existing patterns.
3. Prefer the shared command/action path over new ad hoc logic.
4. Make the smallest coherent change that solves the problem.
5. Run the most targeted verification first, then broader checks if needed.
6. Update docs when commands, workflows, runtime behavior, or parity claims change.

If a prompt sounds like a feature request, do not treat noun phrases as literal file paths. Research first.

## Runtime and Safety Rules

- Keep workspace boundary protections intact.
- Keep readiness/status cheap by default. Heavy validation should stay explicit.
- Preserve rollback behavior for risky or verification-backed flows.
- Do not claim autonomous multi-agent execution is done unless the repo truly has worker isolation, ownership, merge, and verification.
- Be honest about current limits.

## Parity Priorities

When choosing what to improve, prefer work that closes the gap to a strong AI dev assistant:

1. runtime truth and diagnostics
2. research-first routing
3. safe edit/apply/rollback loops
4. VS Code task/tool integration
5. inline editing and useful chat UX
6. learning and self-improvement with real gates
7. clean maintainer handoff and operational docs

## Required Docs Sync

Update the right docs when behavior changes:

- `README.md`: setup, run, user-facing workflows
- `ROADMAP.md`: milestone truth and latest proof log
- `docs/DEV_BOOK.md`: architecture and layering guidance
- `docs/MAINTAINER_PLAYBOOK.md`: maintainership and release workflow
- `docs/COMMAND_BOOK.md`: high-value commands, tasks, endpoints
- `docs/HANDOFF_GUIDE.md`: what the next developer or agent needs
- `docs/COPILOT_LIKE_FLOW_BLUEPRINT.md`: behavior target for parity work
- `docs/SELF_IMPROVEMENT_BASELINE_PACK_V1.md`: self-improvement acceptance gate

## Verification Expectations

For most changes, prefer some subset of:

- `./.venv/bin/python -m pytest -q`
- targeted pytest modules
- `npm --prefix vscode-extension run compile:clean`
- `npm --prefix vscode-extension run test:smoke`
- `npm --prefix vscode-extension run verify:vsix`

If the extension build/install path changes, verify the packaged VSIX instead of trusting the workspace `out/` directory alone.

## Clean Repo Expectations

- Keep diffs focused.
- Do not mix unrelated refactors into feature work.
- Keep generated/runtime artifacts out of commits.
- Batch commits by intent so another developer can review or revert them safely.

## Handoff Standard

Leave the repo in a state where another developer or agent can quickly answer:

- what changed
- why it changed
- how it was verified
- what is still risky
- which docs were updated

If that is not clear, the change is not finished.
