# aicode Thin VS Code Client

This extension is intentionally thin: it forwards prompts to your local aicode app service and renders results in an output channel.

## Commands

- `aicode: Ask` — prompts for a natural-language command and sends it to `POST /v1/aicode/command`
- `aicode: Open Chat Panel` — opens a lightweight webview panel for chat-style interactions backed by `POST /v1/aicode/command`
- `aicode: Check API Status` — verifies local server reachability via a status call

The chat panel includes:
- in-panel command history chips
- one-click `Retry` on each response card

## Setup

1. Start app server:

```bash
poetry run python -m src.server
```

2. Build extension:

```bash
cd vscode-extension
npm install
npm run compile
```

3. Run extension in VS Code:
- Open `vscode-extension` folder
- Press `F5` to launch Extension Development Host
- Run command palette → `aicode: Ask`

## Configuration

- `aicode.baseUrl` (default: `http://127.0.0.1:8005`)
