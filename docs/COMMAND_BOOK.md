# Command Book

## Purpose

This is the quick-reference book for the highest-value commands, tasks, and endpoints in `coding-ai-app`.

Use it when you need to:

- start the system
- verify the repo
- inspect runtime truth
- use self-improvement safely
- operate the VS Code extension

## Core Runtime

### Start Ollama

```bash
ollama serve
```

### Start the local API server

```bash
poetry run python -m src.server
```

### Run a one-shot CLI request

```bash
poetry run python -m src.main "Write a Python function that computes fibonacci(n)."
```

### Run the app-command path directly

```bash
poetry run python -m src.main app-command "status"
```

### Open the terminal UI

```bash
poetry run python -m src.main tui
```

## Runtime Truth and Readiness

### Lightweight status

```bash
poetry run python -m src.main status
```

### Full validation-backed status

```bash
poetry run python -m src.main status --full
```

### Full benchmark/gate

```bash
poetry run python -m src.main benchmark
poetry run python -m src.main gate
```

### Live readiness API

- `GET /healthz`
- `GET /v1/aicode/readiness`
- `POST /v1/aicode/command`

### Self-improvement status APIs

- `GET /v1/aicode/self-improve/runs/latest`
- `GET /v1/aicode/self-improve/runs/{run_id}`

## Safe Edit and Repair

### Edit one file with preview

```bash
poetry run python -m src.main edit src/main.py "Add argparse support and keep behavior the same"
```

### Non-interactive apply

```bash
poetry run python -m src.main edit src/main.py "Add argparse support and keep behavior the same" --yes
```

### Automated repair loop

```bash
poetry run python -m src.main autofix src/main.py "Add argparse support" --tests "python -m pytest -q" --max-attempts 3
```

## Self-Improvement

### Plan only

```bash
poetry run python -m src.main self-improve --cycles 3 --target-score 95
poetry run python -m src.main app-command "self-improve plan add a clear chat button to the VS Code panel"
```

### Status

```bash
poetry run python -m src.main app-command "self-improve status"
```

### Approve/apply a run

```bash
poetry run python -m src.main app-command "approve self-improve <run_id>"
```

Rules:

- planning must be research-first
- apply must stay bounded
- pinned/approved file allowlists must be respected
- failed verification must roll back

## Learning and Live Mode

### Learning baseline and memory

```bash
poetry run python -m src.main project-memory add convention "prefer pytest -q"
poetry run python -m src.main project-memory search pytest
poetry run python -m src.main eval
```

### Continuous learning mode

```bash
poetry run python -m src.main live status
poetry run python -m src.main live --iterations 1 --interval 10
poetry run python -m src.main live --allow-unlocked
```

## Verification

### Full Python suite

```bash
./.venv/bin/python -m pytest -q
```

### Extension verification

```bash
npm --prefix vscode-extension run compile:clean
npm --prefix vscode-extension run test:smoke
npm --prefix vscode-extension run verify:vsix
```

## VS Code Workspace Tasks

The parent workspace `.vscode/tasks.json` is part of the real operator surface.

Important tasks:

- `run:ollama-serve`
- `run:aicode-server`
- `run:aicode-chat`
- `run:aicode-tui`
- `test:aicode-all`
- `build:vscode-extension`
- `watch:vscode-extension`

The extension should prefer these tasks over ad hoc process management when they are available.

## VS Code Extension Commands

High-value extension commands include:

- `aicode: Open Chat Panel`
- `aicode: Check API Status`
- `aicode: Start Local Server`
- `aicode: Restart Local Server`
- `aicode: Stop Local Server`
- `aicode: Start Ollama Task`
- `aicode: Stop Ollama Task`
- `aicode: Run VS Code Task`
- `aicode: Show Action Log`
- `aicode: Edit Current File`
- `aicode: Edit Selection`
- `aicode: Inline Chat`

Additional context-aware commands may exist for problems, SCM, tests, terminal capture, and debug views.

## Packaging and Install

### Package a release build

```bash
npm --prefix vscode-extension run package:release
```

### Verify the VSIX

```bash
npm --prefix vscode-extension run verify:vsix
```

### Install the VSIX

```bash
npm --prefix vscode-extension run install:vsix -- vscode-extension/dist/aicode-local-agent-<version>.vsix
```

## When in Doubt

If you only remember a small set, use these:

1. `./.venv/bin/python -m pytest -q`
2. `poetry run python -m src.main status`
3. `poetry run python -m src.server`
4. `npm --prefix vscode-extension run test:smoke`
5. `npm --prefix vscode-extension run verify:vsix`
