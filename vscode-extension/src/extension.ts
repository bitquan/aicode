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

  context.subscriptions.push(askDisposable, statusDisposable, output);
}

export function deactivate() {}
