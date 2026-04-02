# aicode VS Code Extension

This extension now acts as a managed local client for the Python app instead of only forwarding raw text commands.

## What It Does

- Auto-starts and health-checks the local `src.server` process
- Opens a chat panel with a visible action log
- Adds `Edit Current File` and `Edit Selection` commands with diff preview before apply
- Adds inline editor chat by attaching comment threads to the current selection or line

## Commands

- `aicode: Ask`
- `aicode: Open Chat Panel`
- `aicode: Check API Status`
- `aicode: Restart Local Server`
- `aicode: Show Action Log`
- `aicode: Edit Current File`
- `aicode: Edit Selection`
- `aicode: Inline Chat`

The editor commands are also available from the editor title and context menu.

## Setup

1. Build the extension:

```bash
cd vscode-extension
npm install
npm run compile
npm run test:smoke
```

2. Run the extension in VS Code:
- Open the `coding-ai-app` repo
- Press `F5` to launch the Extension Development Host
- The extension will auto-start the local server unless you disable that in settings

3. Package for normal VS Code:

```bash
cd vscode-extension
npm run package:vsix
```

Then install `dist/aicode-local-agent-0.1.4.vsix` from VS Code with `Extensions: Install from VSIX...`.

## Configuration

- `aicode.baseUrl`
- `aicode.autoStartServer`
- `aicode.serverRoot`
- `aicode.workspaceRoot`
- `aicode.pythonPath`

Defaults are chosen for this repo layout:
- `serverRoot` defaults to the parent of `vscode-extension`
- `workspaceRoot` defaults to `serverRoot`
- `pythonPath` defaults to `.venv/bin/python` when present
