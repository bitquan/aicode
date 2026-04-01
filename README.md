# Coding AI Program (Local Ollama)

Master plan and checklist: [ROADMAP.md](ROADMAP.md)

## Overview
This app generates code from a prompt using a local Ollama model and then performs basic validation by parsing and executing the returned code with a timeout.

## Prerequisites
- Python 3.11+
- Ollama running locally
- A local model, for example `qwen2.5-coder:7b`

## Setup
1. Install dependencies:
   ```bash
   poetry install
   ```
2. Ensure Ollama is running:
   ```bash
   ollama serve
   ```
3. Ensure the model exists:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```

## Run
```bash
poetry run python -m src.main "Write a Python function that computes fibonacci(n)."
```

If no prompt is passed, the CLI asks interactively.

Terminal UI mode (MVP):

```bash
poetry run python -m src.main tui
```

Inside terminal mode: `help`, `capabilities`, `plan ...`, `generate ...`, `edit ...`, `quit`.

Audit events for a trace:

```bash
poetry run python -m src.main audit <trace_id>
```

View blocker and fix-memory data:

```bash
poetry run python -m src.main blocker <trace_id>
poetry run python -m src.main memory <target_path> <failure_category>
```

Repo intelligence and safety helpers:

```bash
poetry run python -m src.main index
poetry run python -m src.main symbols
poetry run python -m src.main search "autofix confidence"
poetry run python -m src.main context "autofix confidence" --chars 2000
poetry run python -m src.main read src/main.py
poetry run python -m src.main validate-diff src/main.py
```

Workflow parity and learning helpers:

```bash
poetry run python -m src.main mode explain "why this test fails"
poetry run python -m src.main debug-guide "intermittent timeout in pytest"
poetry run python -m src.main notebook-guide "clean notebook state and rerun cells"
poetry run python -m src.main task-plan "add config validation"
poetry run python -m src.main doc-update src/main.py src/tools/autofix.py
poetry run python -m src.main project-memory add convention "prefer pytest -q"
poetry run python -m src.main project-memory get convention
poetry run python -m src.main project-memory search pytest
poetry run python -m src.main policy-recommend autofix "python -m pytest -q"
poetry run python -m src.main eval
```

Governance and operations helpers:

```bash
poetry run python -m src.main gate
poetry run python -m src.main telemetry
poetry run python -m src.main release-notes 0.2.0
poetry run python -m src.main audit-export <trace_id>
poetry run python -m src.main retention-clean --days 14
poetry run python -m src.main deps
poetry run python -m src.main license-scan
poetry run python -m src.main playbooks scaffold
poetry run python -m src.main playbooks status
poetry run python -m src.main compliance
poetry run python -m src.main budget show
poetry run python -m src.main budget set max_gate_seconds 120
poetry run python -m src.main budget check
poetry run python -m src.main budget metrics 20
poetry run python -m src.main cost-estimate 1000 500
poetry run python -m src.main cost-summary
poetry run python -m src.main cost-by-trace
poetry run python -m src.main policy-check edit --role developer --auto
poetry run python -m src.main resume-autofix <trace_id>
poetry run python -m src.main incident-timeline <trace_id>
poetry run python -m src.main incident-report <trace_id>
poetry run python -m src.main postmortem <trace_id>
poetry run python -m src.main gate --profile strict
poetry run python -m src.main benchmark --profile strict
poetry run python -m src.main status
poetry run python -m src.main status-export
poetry run python -m src.main self-improve --cycles 3 --target-score 95
```

## Edit a File (Patch Workflow)
Use the model to rewrite a specific file from an instruction:

```bash
poetry run python -m src.main edit src/main.py "Add argparse support and keep behavior the same"
```

This prints a unified diff preview and asks for confirmation.

For non-interactive apply:

```bash
poetry run python -m src.main edit src/main.py "Add argparse support and keep behavior the same" --yes
```

Safety rule: target path must stay inside the current workspace.

## Auto Verify-and-Fix Loop
Run an automated repair loop on one file:

```bash
poetry run python -m src.main autofix src/main.py "Add argparse support" --tests "python -m pytest -q" --max-attempts 3
```

Extra flags:
- `--multi` enables related-file rewrite attempts for planned companion files.
- `--no-flaky-confirm` disables flaky confirmation rerun.

This command applies iterative file edits, runs tests, and rolls back to original content if all attempts fail.
It also classifies failures (for example: syntax, dependency, timeout, runtime) to guide smarter repair prompts on retry.

## Test
```bash
poetry run pytest -q
```

## Notes
- Default model: `qwen2.5-coder:7b`
- Default Ollama URL: `http://127.0.0.1:11434`
- Profile config lives in `src/config/profiles.json` (`local`, `dev`, `prod`) and is selected with `APP_PROFILE`.
- Retry and timeout behavior can be overridden with `OLLAMA_TIMEOUT`, `OLLAMA_MAX_RETRIES`, and `OLLAMA_RETRY_BACKOFF`.

## Autofix Behavior Details
- If `--tests` is omitted, the tool auto-selects targeted tests (e.g. `src/foo.py` → `tests/test_foo.py` when present).
- Each autofix run emits JSON trace logs with a trace ID and writes JSONL audit data to `.autofix_reports/audit/<trace_id>.jsonl`.
- Autofix uses failure-category strategy routing to adjust repair instructions (syntax/dependency/runtime/etc.).
- A circuit-breaker stops early on repeated failure categories.
- If attempts fail, the file is rolled back, blocker report is written to `.autofix_reports/<trace_id>.json`, and a minimal repro file is generated at `.autofix_reports/<trace_id>_repro.md`.
- Flaky signals are detected from failure output (rerun/intermittent markers) and routed through a flaky strategy.
- Repair planning now tracks related files (target + traceback/test companions) for multi-file awareness.
- Fix memory is persisted in `.autofix_reports/fix_memory.jsonl` and reused as hints in later repairs.
- Autofix reports confidence scores and can switch to focused pytest node-id reruns when node IDs are detected.

## OpenAI-Compatible Local API Server

The repo ships a FastAPI server that exposes an OpenAI-compatible HTTP API backed by your local Ollama model.

### Start the server

```bash
poetry run python -m src.server
```

The server listens on port **8005** by default. Override with the `PORT` environment variable:

```bash
PORT=9000 poetry run python -m src.server
```

Other relevant environment variables (same as CLI):
- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `qwen2.5-coder:7b`)
- `WORKSPACE_ROOT` — root directory used by file tools (default: current working directory)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat (streaming + tool calling) |

### Example: curl

```bash
curl http://127.0.0.1:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "Write a Python hello-world function."}],
    "stream": false
  }'
```

Streaming example:

```bash
curl http://127.0.0.1:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [{"role": "user", "content": "Explain async/await in Python."}],
    "stream": true
  }'
```

### Example: Python OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8005/v1",
    api_key="ollama",  # any non-empty string
)

response = client.chat.completions.create(
    model="qwen2.5-coder:7b",
    messages=[{"role": "user", "content": "Read the file src/main.py and summarise it."}],
)
print(response.choices[0].message.content)
```

Streaming with the SDK:

```python
stream = client.chat.completions.create(
    model="qwen2.5-coder:7b",
    messages=[{"role": "user", "content": "Run the tests and tell me if they pass."}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

### Built-in tools

The server automatically provides the model with these workspace tools (no extra client configuration needed):

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read a file relative to `WORKSPACE_ROOT` |
| `search(query)` | Search repository files for relevant snippets |
| `run_tests(command)` | Execute a test command (e.g. `pytest tests/`) |
| `edit_file(path, instruction)` | Rewrite a file using a plain-English instruction |

Pass `"tool_choice": "none"` to disable tool calling for a request.

## Source of Truth Architecture (App + Thin Extension)

The app is the source of truth. Both CLI and API call the same shared service layer:

- Shared service: `src/app_service.py`
- CLI entry: `python -m src.main app-command "<natural language command>"`
- API entry: `POST /v1/aicode/command`

This keeps behavior centralized and avoids duplicating logic in editor clients.

### App command API example

```bash
curl http://127.0.0.1:8005/v1/aicode/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}'
```

### Thin VS Code extension

A thin extension client is included in `vscode-extension/`. It sends commands to `/v1/aicode/command` and renders responses in a VS Code output channel.

Build/run:

```bash
cd vscode-extension
npm install
npm run compile
```

Then open `vscode-extension` in VS Code and press `F5`.

## Prompt Layers
Prompts are now layered from:
- `src/prompts/system_prompt.txt`
- `src/prompts/developer_prompt.txt`
- `src/prompts/tool_prompt.txt`