import * as vscode from 'vscode';

type AppCommandResponse = {
  command: string;
  action: string;
  confidence: number;
  response: string;
};

function baseUrl(): string {
  const config = vscode.workspace.getConfiguration('aicode');
  return String(config.get('baseUrl', 'http://127.0.0.1:8005')).replace(/\/$/, '');
}

async function callAppCommand(command: string): Promise<AppCommandResponse> {
  const url = `${baseUrl()}/v1/aicode/command`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command }),
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${detail}`);
  }
  return (await resp.json()) as AppCommandResponse;
}

function panelHtml(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>aicode Chat</title>
  <style>
    body { font-family: var(--vscode-font-family); padding: 12px; color: var(--vscode-foreground); }
    #history { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 10px; height: 50vh; overflow: auto; white-space: pre-wrap; }
    .row { margin-top: 10px; display: flex; gap: 8px; }
    input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 8px; border-radius: 4px; }
    button { padding: 8px 12px; border: 1px solid var(--vscode-button-border, transparent); background: var(--vscode-button-background); color: var(--vscode-button-foreground); border-radius: 4px; cursor: pointer; }
    .meta { opacity: 0.8; font-size: 12px; }
  </style>
</head>
<body>
  <h3>aicode Chat Panel</h3>
  <div class="meta">Thin client: requests are sent to local app API.</div>
  <div id="history"></div>
  <div class="row">
    <input id="prompt" placeholder="e.g. security scan src/ or status" />
    <button id="send">Send</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const history = document.getElementById('history');
    const input = document.getElementById('prompt');
    const send = document.getElementById('send');

    function append(line) {
      history.textContent += line + "\n\n";
      history.scrollTop = history.scrollHeight;
    }

    function submit() {
      const value = input.value.trim();
      if (!value) return;
      append('> ' + value);
      vscode.postMessage({ type: 'ask', command: value });
      input.value = '';
      input.focus();
    }

    send.addEventListener('click', submit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'result') {
        append('[action=' + msg.action + ', confidence=' + msg.confidence + ']\\n' + msg.response);
      }
      if (msg.type === 'error') {
        append('ERROR: ' + msg.message);
      }
    });
  </script>
</body>
</html>`;
}

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('aicode');

  const askDisposable = vscode.commands.registerCommand('aicode.ask', async () => {
    const command = await vscode.window.showInputBox({
      prompt: 'Ask aicode (uses local app API)',
      placeHolder: 'e.g. security scan src/ or status',
      ignoreFocusOut: true,
    });

    if (!command) {
      return;
    }

    try {
      const result = await callAppCommand(command);
      output.show(true);
      output.appendLine(`> ${result.command}`);
      output.appendLine(`[action=${result.action}, confidence=${result.confidence}]`);
      output.appendLine(result.response);
      output.appendLine('');
      vscode.window.showInformationMessage(`aicode: ${result.action}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      vscode.window.showErrorMessage(`aicode request failed: ${message}`);
    }
  });

  const statusDisposable = vscode.commands.registerCommand('aicode.status', async () => {
    try {
      await callAppCommand('status');
      vscode.window.showInformationMessage('aicode API is reachable.');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      vscode.window.showWarningMessage(`aicode API not reachable: ${message}`);
    }
  });

  const panelDisposable = vscode.commands.registerCommand('aicode.openPanel', async () => {
    const panel = vscode.window.createWebviewPanel(
      'aicodeChatPanel',
      'aicode Chat',
      vscode.ViewColumn.Beside,
      { enableScripts: true },
    );

    panel.webview.html = panelHtml();

    panel.webview.onDidReceiveMessage(async (message) => {
      if (message?.type !== 'ask') {
        return;
      }
      const command = String(message.command || '').trim();
      if (!command) {
        return;
      }

      try {
        const result = await callAppCommand(command);
        panel.webview.postMessage({
          type: 'result',
          action: result.action,
          confidence: result.confidence,
          response: result.response,
        });
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        panel.webview.postMessage({ type: 'error', message: text });
      }
    });
  });

  context.subscriptions.push(askDisposable, statusDisposable, panelDisposable, output);
}

export function deactivate() {}
