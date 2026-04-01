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

function commandUrl(): string {
  return `${baseUrl()}/v1/aicode/command`;
}

async function callAppCommand(command: string): Promise<AppCommandResponse> {
  const url = commandUrl();
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

async function checkApiHealth(): Promise<void> {
  const url = commandUrl();
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command: 'status' }),
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`Health check failed at ${url} (HTTP ${resp.status}): ${detail}`);
  }
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
    #history { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 10px; height: 50vh; overflow: auto; }
    .entry { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 8px; margin-bottom: 8px; }
    .prompt { font-weight: 600; margin-bottom: 6px; white-space: pre-wrap; }
    .reply { white-space: pre-wrap; margin-bottom: 8px; }
    .entry-actions { display: flex; justify-content: flex-end; }
    .row { margin-top: 10px; display: flex; gap: 8px; }
    input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 8px; border-radius: 4px; }
    button { padding: 8px 12px; border: 1px solid var(--vscode-button-border, transparent); background: var(--vscode-button-background); color: var(--vscode-button-foreground); border-radius: 4px; cursor: pointer; }
    #recent { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { font-size: 12px; padding: 4px 8px; }
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
    <button id="health">Check API</button>
  </div>
  <div id="recent"></div>

  <script>
    const vscode = acquireVsCodeApi();
    const history = document.getElementById('history');
    const recent = document.getElementById('recent');
    const input = document.getElementById('prompt');
    const send = document.getElementById('send');
    const health = document.getElementById('health');
    const state = vscode.getState() || { commands: [] };
    let commandHistory = Array.isArray(state.commands) ? state.commands : [];

    function rememberCommand(command) {
      const next = [command, ...commandHistory.filter((item) => item !== command)];
      commandHistory = next.slice(0, 8);
      vscode.setState({ commands: commandHistory });
      renderRecent();
    }

    function renderRecent() {
      recent.innerHTML = '';
      if (!commandHistory.length) {
        return;
      }
      for (const command of commandHistory) {
        const button = document.createElement('button');
        button.className = 'chip';
        button.textContent = 'Retry: ' + command;
        button.title = command;
        button.addEventListener('click', () => submit(command));
        recent.appendChild(button);
      }
    }

    function appendEntry(command, body) {
      const card = document.createElement('div');
      card.className = 'entry';

      const prompt = document.createElement('div');
      prompt.className = 'prompt';
      prompt.textContent = '> ' + command;

      const reply = document.createElement('div');
      reply.className = 'reply';
      reply.textContent = body;

      const actions = document.createElement('div');
      actions.className = 'entry-actions';
      const retry = document.createElement('button');
      retry.textContent = 'Retry';
      retry.addEventListener('click', () => submit(command));
      actions.appendChild(retry);

      card.appendChild(prompt);
      card.appendChild(reply);
      card.appendChild(actions);
      history.appendChild(card);
      history.scrollTop = history.scrollHeight;
    }

    function submit(commandOverride) {
      const value = typeof commandOverride === 'string' ? commandOverride : input.value.trim();
      if (!value) return;
      rememberCommand(value);
      vscode.postMessage({ type: 'ask', command: value });
      if (!commandOverride) {
        input.value = '';
      }
      input.focus();
    }

    send.addEventListener('click', submit);
    health.addEventListener('click', () => {
      vscode.postMessage({ type: 'health' });
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'result') {
        appendEntry(msg.command || 'unknown', '[action=' + msg.action + ', confidence=' + msg.confidence + ']\\n' + msg.response);
      }
      if (msg.type === 'error') {
        appendEntry(msg.command || 'unknown', 'ERROR: ' + msg.message);
      }
      if (msg.type === 'health') {
        appendEntry('health', msg.message);
      }
    });

    renderRecent();
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
      vscode.window.showErrorMessage(`aicode request failed (${commandUrl()}): ${message}`);
    }
  });

  const statusDisposable = vscode.commands.registerCommand('aicode.status', async () => {
    try {
      await checkApiHealth();
      vscode.window.showInformationMessage(`aicode API is reachable (${commandUrl()}).`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      vscode.window.showWarningMessage(`aicode API not reachable (${commandUrl()}): ${message}`);
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
      if (message?.type === 'health') {
        try {
          await checkApiHealth();
          panel.webview.postMessage({ type: 'health', message: `API OK: ${commandUrl()}` });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          panel.webview.postMessage({ type: 'health', message: `API ERROR: ${text}` });
        }
        return;
      }

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
          command,
          action: result.action,
          confidence: result.confidence,
          response: result.response,
        });
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        panel.webview.postMessage({ type: 'error', command, message: text });
      }
    });
  });

  context.subscriptions.push(askDisposable, statusDisposable, panelDisposable, output);
}

export function deactivate() {}
