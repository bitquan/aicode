# Maintainer Playbook

## Purpose

This playbook is for the person keeping `coding-ai-app` healthy over time.

It covers:

- keeping the tree clean
- batching changes into sane commits
- keeping docs in sync
- shipping the VS Code extension safely
- protecting the repo while pushing toward parity

## Source of Truth Order

When there is confusion, check in this order:

1. current code behavior
2. tests
3. runtime manifests and readiness canaries
4. README and command docs
5. roadmap and baseline docs

Do not let docs outrun code, and do not let code drift without updating docs.

## Clean Tree Policy

- Start from a clean tree when possible.
- If there are unrelated local changes, do not overwrite them.
- Commit by intent, not by timestamp.
- Avoid "catch-all" commits that mix UX, backend, docs, and runtime state unless the changes are inseparable.

Good commit batches:

- backend behavior and tests
- extension UX/runtime integrity
- docs and roadmap sync
- release packaging/install updates

## Verification Matrix

### Backend changes

- targeted pytest modules first
- `./.venv/bin/python -m pytest -q` if shared behavior changed

### Extension changes

- `npm --prefix vscode-extension run compile:clean`
- `npm --prefix vscode-extension run test:smoke`
- `npm --prefix vscode-extension run verify:vsix`

### Runtime/build packaging changes

- verify packaged VSIX contents
- install the verified VSIX
- reload VS Code and confirm the panel/runtime data is truthful

## VS Code Extension Release Workflow

Use the packaged VSIX as the authoritative installed artifact.

Recommended flow:

1. `npm --prefix vscode-extension run compile:clean`
2. `npm --prefix vscode-extension run test:smoke`
3. `npm --prefix vscode-extension run verify:vsix`
4. `npm --prefix vscode-extension run package:release`
5. `npm --prefix vscode-extension run install:vsix -- <path-to-vsix>`
6. Reload VS Code and re-check runtime details in the panel

Do not assume the workspace `out/` directory matches the installed extension.

## Docs Sync Rules

Update these docs when the matching behavior changes:

- `README.md`: setup, run, extension usage, user-facing flows
- `ROADMAP.md`: milestone truth and latest proof log
- `docs/DEV_BOOK.md`: architecture/layering rules
- `docs/COMMAND_BOOK.md`: commands/tasks/endpoints
- `docs/HANDOFF_GUIDE.md`: transfer checklist and open risks
- `.github/copilot-instructions.md`: AI contributor guidance

## Runtime Truth Checks

The repo should be able to answer these questions quickly:

- which extension build is loaded
- which server runtime is running
- whether Ollama is reachable
- whether the panel is stale or mismatched
- whether self-improvement is supervised or allowed to apply

If the UI says `unknown` but the backend is healthy, treat that as an extension/runtime integrity bug, not just a UX annoyance.

## Parity Program Rules

When prioritizing work toward Codex/Copilot parity, prefer:

1. runtime truth
2. research-first routing
3. safe bounded edits
4. verification and rollback
5. IDE-native workflow quality
6. learning that changes later behavior
7. honest capability boundaries

Do not claim parity for:

- autonomous multi-agent execution
- fully trusted self-upgrading behavior
- end-to-end IDE workflow reliability

until tests and live behavior prove it.

## Incident Triage

### Panel looks alive but buttons do nothing

Check:

- webview console errors
- installed extension version vs workspace version
- bundled `build_manifest.json`
- whether the panel script actually parsed

### Backend says server is down while `/healthz` is green

Check:

- recursive self-probing
- stale runtime state
- help/status summary composition

### Extension status says `unknown`

Check:

- init/ready handshake
- queued message flush
- runtime build comparison
- stale VS Code window session

## Release Handoff Checklist

Before handing work to another maintainer:

- tree is clean or intentional changes are explained
- verification commands are listed
- docs are updated
- open risks are written down
- packaged artifact version is clear
- the latest runtime truth is easy to inspect

## Current Honest Boundary

Today, `coding-ai-app` is best described as:

- a strong local-first coding assistant foundation
- a supervised self-improvement system with gating
- a growing VS Code IDE workflow

It is not yet a fully autonomous, trusted, multi-agent coding system. Maintain the repo with that truth in mind.
