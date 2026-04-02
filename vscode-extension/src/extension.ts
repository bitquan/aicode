import { ChildProcess, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

import * as vscode from 'vscode';

type ActionEvent = {
  kind: string;
  message: string;
};

type ActionLogEntry = ActionEvent & {
  source: string;
  timestamp: string;
};

type AppCommandResponse = {
  command: string;
  action: string;
  confidence: number;
  response: string;
  events?: ActionEvent[];
};

type OllamaHealth = {
  reachable: boolean;
  detail: string;
  model_available: boolean;
};

type HealthResponse = {
  status: string;
  workspace_root: string;
  model: string;
  base_url: string;
  ollama: OllamaHealth;
};

type EditorPosition = {
  line: number;
  character: number;
};

type EditorRange = {
  start: EditorPosition;
  end: EditorPosition;
};

type EditorChatRequest = {
  path: string;
  prompt: string;
  current_content: string;
  selection?: EditorRange;
};

type EditorChatResponse = {
  path: string;
  prompt: string;
  response: string;
  events?: ActionEvent[];
};

type EditorEditPreviewRequest = {
  path: string;
  instruction: string;
  current_content: string;
  selection?: EditorRange;
};

type EditorEditPreviewResponse = {
  path: string;
  mode: string;
  updated_content: string;
  diff: string;
  replacement_text?: string | null;
  events?: ActionEvent[];
};

type ServerStatusSnapshot = {
  text: string;
  detail: string;
  healthy: boolean;
};

type StreamEventPayload = Record<string, unknown>;

type StreamEvent = {
  event: string;
  data: StreamEventPayload;
};

type StreamCallbacks = {
  onRoute?: (payload: StreamEventPayload) => void;
  onStatus?: (payload: StreamEventPayload) => void;
  onEvent?: (payload: StreamEventPayload) => void;
  onResult?: (payload: StreamEventPayload) => void;
  onDelta?: (payload: StreamEventPayload) => void;
  onDone?: (payload: StreamEventPayload) => void;
};

function getConfiguration(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration('aicode');
}

function normalizeBaseUrl(): string {
  return String(getConfiguration().get('baseUrl', 'http://127.0.0.1:8005')).replace(/\/$/, '');
}

function commandUrl(): string {
  return `${normalizeBaseUrl()}/v1/aicode/command`;
}

function streamCommandUrl(): string {
  return `${normalizeBaseUrl()}/v1/aicode/command/stream`;
}

function healthUrl(): string {
  return `${normalizeBaseUrl()}/healthz`;
}

function editorChatUrl(): string {
  return `${normalizeBaseUrl()}/v1/aicode/editor/chat`;
}

function editorPreviewUrl(): string {
  return `${normalizeBaseUrl()}/v1/aicode/editor/preview-edit`;
}

function defaultOllamaBaseUrl(): string {
  return String(process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '');
}

async function fetchJson<T>(url: string, init?: RequestInit, timeoutMs = 5000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(url, { ...init, signal: controller.signal });
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${detail}`);
    }
    return (await resp.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isValidServerRoot(candidate: string): boolean {
  return fs.existsSync(path.join(candidate, 'src', 'server.py'));
}

function safeStatIsDirectory(candidate: string): boolean {
  try {
    return fs.statSync(candidate).isDirectory();
  } catch {
    return false;
  }
}

async function checkOllamaHealth(baseUrl: string, timeoutMs = 1500): Promise<OllamaHealth> {
  try {
    const payload = await fetchJson<{ models?: Array<{ model?: string; name?: string }> }>(
      `${baseUrl.replace(/\/$/, '')}/api/tags`,
      undefined,
      timeoutMs,
    );
    return {
      reachable: true,
      detail: 'reachable',
      model_available: Array.isArray(payload.models),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      reachable: false,
      detail: message,
      model_available: false,
    };
  }
}

function parseSseBlock(block: string): StreamEvent | undefined {
  const lines = block.split(/\r?\n/);
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(':')) {
      continue;
    }
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim());
    }
  }

  if (!dataLines.length) {
    return undefined;
  }

  try {
    return {
      event,
      data: JSON.parse(dataLines.join('\n')) as StreamEventPayload,
    };
  } catch {
    return {
      event,
      data: { text: dataLines.join('\n') },
    };
  }
}

function normalizeOllamaHealth(
  health: Partial<HealthResponse> | undefined,
  fallbackBaseUrl?: string,
): OllamaHealth {
  const candidate = (health as { ollama?: Partial<OllamaHealth> } | undefined)?.ollama;
  return {
    reachable: Boolean(candidate?.reachable),
    detail:
      typeof candidate?.detail === 'string'
        ? candidate.detail
        : `unknown (using ${fallbackBaseUrl ?? defaultOllamaBaseUrl()})`,
    model_available: Boolean(candidate?.model_available),
  };
}

class ActionLogStore implements vscode.Disposable {
  private readonly entries: ActionLogEntry[] = [];
  private readonly emitter = new vscode.EventEmitter<readonly ActionLogEntry[]>();

  readonly onDidChange = this.emitter.event;

  constructor(private readonly output: vscode.OutputChannel) {}

  append(kind: string, message: string, source = 'extension'): void {
    const entry: ActionLogEntry = {
      kind,
      message,
      source,
      timestamp: new Date().toISOString(),
    };
    this.entries.unshift(entry);
    if (this.entries.length > 80) {
      this.entries.length = 80;
    }
    this.output.appendLine(`[${entry.timestamp}] [${entry.source}] [${entry.kind}] ${entry.message}`);
    this.emitter.fire(this.getEntries());
  }

  appendMany(events: ActionEvent[] | undefined, source = 'server'): void {
    for (const event of events ?? []) {
      this.append(event.kind, event.message, source);
    }
  }

  getEntries(): readonly ActionLogEntry[] {
    return [...this.entries];
  }

  dispose(): void {
    this.emitter.dispose();
  }
}

class ServerManager implements vscode.Disposable {
  private child: ChildProcess | undefined;
  private startedByExtension = false;
  private readonly statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  private readonly emitter = new vscode.EventEmitter<ServerStatusSnapshot>();
  private readonly healthTimer: ReturnType<typeof setInterval>;
  private lastOutputLines: string[] = [];
  private lastExitDetail = 'No server process launched yet.';
  private lastHealth: HealthResponse | undefined;
  private status: ServerStatusSnapshot = {
    text: '$(circle-large-outline) aicode',
    detail: `Server not connected (${healthUrl()})`,
    healthy: false,
  };

  readonly onDidChangeStatus = this.emitter.event;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly output: vscode.OutputChannel,
    private readonly actionLog: ActionLogStore,
  ) {
    this.statusBar.command = 'aicode.status';
    this.statusBar.tooltip = this.status.detail;
    this.statusBar.text = this.status.text;
    this.statusBar.show();

    this.healthTimer = setInterval(() => {
      void this.refreshHealth(false);
    }, 15000);
  }

  baseUrl(): string {
    return normalizeBaseUrl();
  }

  autoStartEnabled(): boolean {
    return Boolean(getConfiguration().get('autoStartServer', true));
  }

  getStatus(): ServerStatusSnapshot {
    return { ...this.status };
  }

  async ensureRunning(): Promise<HealthResponse> {
    const healthy = await this.refreshHealth(false);
    if (healthy) {
      return healthy;
    }

    if (!this.autoStartEnabled()) {
      throw new Error(await this.buildDiagnosticsMessage('aicode server is not reachable and auto-start is disabled.'));
    }

    await this.startServer();
    return this.waitForHealthy();
  }

  async ensureModelReady(): Promise<HealthResponse> {
    const health = await this.ensureRunning();
    const ollama = normalizeOllamaHealth(health, health.base_url);
    if (!ollama.reachable) {
      throw new Error(
        await this.buildDiagnosticsMessage(
          `aicode server is reachable, but Ollama is not ready: ${ollama.detail}`,
        ),
      );
    }
    return { ...health, ollama };
  }

  async restart(): Promise<HealthResponse> {
    this.actionLog.append('server', 'Restart requested', 'extension');

    if (this.child && this.child.exitCode === null) {
      await this.stopManagedProcess();
    } else {
      const healthy = await this.refreshHealth(false);
      if (healthy) {
        this.actionLog.append(
          'server',
          'Server is externally managed and already healthy; keeping the current process.',
          'extension',
        );
        return healthy;
      }
    }

    await this.startServer();
    return this.waitForHealthy();
  }

  private configBaseDir(): string {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? this.context.extensionPath;
  }

  private workspaceFolderPaths(): string[] {
    return (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath);
  }

  private detectServerRoot(): string | undefined {
    const workspaceFolders = this.workspaceFolderPaths();
    const candidates = new Set<string>();

    for (const folder of workspaceFolders) {
      candidates.add(folder);
      candidates.add(path.join(folder, 'coding-ai-app'));

      try {
        const children = fs.readdirSync(folder, { withFileTypes: true });
        for (const child of children) {
          if (!child.isDirectory()) {
            continue;
          }
          const childPath = path.join(folder, child.name);
          candidates.add(childPath);
          candidates.add(path.join(childPath, 'coding-ai-app'));
        }
      } catch {
        // Ignore unreadable folders; diagnostics will cover the final resolution.
      }
    }

    const devRoot = path.resolve(this.context.extensionPath, '..');
    candidates.add(devRoot);

    for (const candidate of candidates) {
      if (isValidServerRoot(candidate)) {
        return candidate;
      }
    }

    return undefined;
  }

  private resolveConfiguredPath(value: string | undefined, fallback: string): string {
    const trimmed = String(value ?? '').trim();
    if (!trimmed) {
      return fallback;
    }
    return path.isAbsolute(trimmed) ? trimmed : path.resolve(this.configBaseDir(), trimmed);
  }

  private resolveServerRoot(): string {
    const configured = String(getConfiguration().get<string>('serverRoot') ?? '').trim();
    if (configured) {
      return this.resolveConfiguredPath(configured, this.configBaseDir());
    }
    const detected = this.detectServerRoot();
    if (detected) {
      return detected;
    }
    return this.configBaseDir();
  }

  private resolveWorkspaceRoot(): string {
    const configured = String(getConfiguration().get<string>('workspaceRoot') ?? '').trim();
    if (configured) {
      return this.resolveConfiguredPath(configured, this.resolveServerRoot());
    }
    return this.resolveServerRoot();
  }

  private resolvePythonPath(): string {
    const configured = String(getConfiguration().get('pythonPath', '')).trim();
    if (configured) {
      return path.isAbsolute(configured) ? configured : path.resolve(this.configBaseDir(), configured);
    }

    const serverRoot = this.resolveServerRoot();
    const candidates = [
      path.join(serverRoot, '.venv', 'bin', 'python'),
      path.join(serverRoot, '.venv', 'Scripts', 'python.exe'),
    ];
    const existing = candidates.find((candidate) => fs.existsSync(candidate));
    return existing ?? 'python3';
  }

  private updateStatus(text: string, detail: string, healthy: boolean): void {
    this.status = { text, detail, healthy };
    this.statusBar.text = text;
    this.statusBar.tooltip = detail;
    this.statusBar.backgroundColor = healthy
      ? undefined
      : new vscode.ThemeColor('statusBarItem.warningBackground');
    this.emitter.fire(this.getStatus());
  }

  private currentLaunchConfig(): {
    pythonPath: string;
    serverRoot: string;
    workspaceRoot: string;
    launchCommand: string;
  } {
    const pythonPath = this.resolvePythonPath();
    const serverRoot = this.resolveServerRoot();
    const workspaceRoot = this.resolveWorkspaceRoot();
    return {
      pythonPath,
      serverRoot,
      workspaceRoot,
      launchCommand: `${pythonPath} -m src.server`,
    };
  }

  private rememberOutput(source: 'stdout' | 'stderr', chunk: Buffer | string): void {
    const lines = String(chunk)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => `[${source}] ${line}`);
    if (!lines.length) {
      return;
    }
    this.lastOutputLines.push(...lines);
    if (this.lastOutputLines.length > 30) {
      this.lastOutputLines.splice(0, this.lastOutputLines.length - 30);
    }
  }

  private async buildDiagnosticsMessage(reason: string): Promise<string> {
    const launch = this.currentLaunchConfig();
    const ollama =
      this.lastHealth?.ollama && typeof this.lastHealth.ollama === 'object'
        ? normalizeOllamaHealth(this.lastHealth, this.lastHealth.base_url)
        : await checkOllamaHealth(this.lastHealth?.base_url ?? defaultOllamaBaseUrl());
    const ollamaBase = this.lastHealth?.base_url ?? defaultOllamaBaseUrl();
    const lines = [
      reason,
      `Server URL: ${this.baseUrl()}`,
      `Python: ${launch.pythonPath}`,
      `Server root: ${launch.serverRoot}`,
      `Workspace root: ${launch.workspaceRoot}`,
      `Launch command: ${launch.launchCommand}`,
      `Last process exit: ${this.lastExitDetail}`,
      `Ollama URL: ${ollamaBase}`,
      `Ollama status: ${ollama.reachable ? 'reachable' : 'unreachable'} (${ollama.detail})`,
    ];
    if (this.lastOutputLines.length) {
      lines.push('Recent server output:');
      lines.push(...this.lastOutputLines.slice(-8));
    }
    return lines.join('\n');
  }

  async showDiagnostics(reason: string): Promise<string> {
    const diagnostics = await this.buildDiagnosticsMessage(reason);
    this.output.appendLine('=== aicode diagnostics ===');
    this.output.appendLine(diagnostics);
    this.output.appendLine('==========================');
    this.output.show(true);
    return diagnostics;
  }

  private wireChildProcess(child: ChildProcess): void {
    child.stdout?.on('data', (chunk: Buffer | string) => {
      this.rememberOutput('stdout', chunk);
      this.output.append(String(chunk));
    });
    child.stderr?.on('data', (chunk: Buffer | string) => {
      this.rememberOutput('stderr', chunk);
      this.output.append(String(chunk));
    });
    child.on('error', (error) => {
      this.actionLog.append('server', `Failed to start server: ${error.message}`, 'extension');
      this.lastExitDetail = `Spawn error: ${error.message}`;
      this.updateStatus('$(error) aicode', `Server failed to start: ${error.message}`, false);
    });
    child.on('exit', (code, signal) => {
      this.child = undefined;
      const detail = `Server exited${code !== null ? ` with code ${code}` : ''}${signal ? ` (${signal})` : ''}`;
      this.lastExitDetail = detail;
      this.actionLog.append('server', detail, 'extension');
      this.updateStatus('$(warning) aicode', detail, false);
      this.startedByExtension = false;
    });
  }

  async refreshHealth(showErrors: boolean): Promise<HealthResponse | undefined> {
    try {
      const rawHealth = await fetchJson<Partial<HealthResponse>>(healthUrl(), undefined, 1500);
      const health: HealthResponse = {
        status: String(rawHealth.status ?? 'ok'),
        workspace_root: String(rawHealth.workspace_root ?? this.resolveWorkspaceRoot()),
        model: String(rawHealth.model ?? 'unknown'),
        base_url: String(rawHealth.base_url ?? defaultOllamaBaseUrl()),
        ollama:
          rawHealth.ollama && typeof rawHealth.ollama === 'object'
            ? normalizeOllamaHealth(rawHealth as HealthResponse, String(rawHealth.base_url ?? defaultOllamaBaseUrl()))
            : await checkOllamaHealth(String(rawHealth.base_url ?? defaultOllamaBaseUrl())),
      };
      this.lastHealth = health;
      const ollamaDetail = health.ollama.reachable
        ? `Ollama ready (${health.model})`
        : `Ollama unavailable (${health.ollama.detail})`;
      this.updateStatus(
        health.ollama.reachable ? '$(check) aicode' : '$(warning) aicode',
        `Server ready at ${this.baseUrl()} using ${health.model}. ${ollamaDetail}`,
        health.ollama.reachable,
      );
      return health;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.lastHealth = undefined;
      this.updateStatus('$(warning) aicode', `Server not reachable: ${message}`, false);
      if (showErrors) {
        const choice = await vscode.window.showWarningMessage(
          `aicode server not reachable (${this.baseUrl()}): ${message}`,
          'Restart Server',
          'Open Diagnostics',
        );
        if (choice === 'Restart Server') {
          void this.restart();
        } else if (choice === 'Open Diagnostics') {
          await this.showDiagnostics(`Server not reachable: ${message}`);
        }
      }
      return undefined;
    }
  }

  async startServer(): Promise<void> {
    if (this.child && this.child.exitCode === null) {
      return;
    }

    const { pythonPath, serverRoot, workspaceRoot, launchCommand } = this.currentLaunchConfig();
    if (!isValidServerRoot(serverRoot)) {
      throw new Error(
        await this.buildDiagnosticsMessage(
          'Could not find the aicode app root. Open the repo workspace or set aicode.serverRoot explicitly.',
        ),
      );
    }

    this.actionLog.append('server', `Starting local server in ${serverRoot}`, 'extension');
    this.output.appendLine(`$ ${launchCommand}`);
    this.lastOutputLines = [];
    this.lastExitDetail = 'Server launch in progress.';
    this.updateStatus('$(sync~spin) aicode', `Starting local server in ${serverRoot}`, false);

    const child = spawn(pythonPath, ['-m', 'src.server'], {
      cwd: serverRoot,
      env: {
        ...process.env,
        WORKSPACE_ROOT: workspaceRoot,
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.child = child;
    this.startedByExtension = true;
    this.wireChildProcess(child);
  }

  private async stopManagedProcess(): Promise<void> {
    if (!this.child || this.child.exitCode !== null) {
      this.child = undefined;
      return;
    }

    const child = this.child;
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, 3000);
      child.once('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
      child.kill();
    });
  }

  private async waitForHealthy(): Promise<HealthResponse> {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 30000) {
      const health = await this.refreshHealth(false);
      if (health) {
        return health;
      }
      await sleep(750);
    }
    throw new Error(await this.buildDiagnosticsMessage(`Timed out waiting for aicode server at ${this.baseUrl()}.`));
  }

  dispose(): void {
    clearInterval(this.healthTimer);
    this.statusBar.dispose();
    this.emitter.dispose();
    if (this.startedByExtension && this.child && this.child.exitCode === null) {
      this.child.kill();
    }
  }
}

function toServerRelativePath(fileUri: vscode.Uri, workspaceRoot: string): string {
  const relative = path.relative(path.resolve(workspaceRoot), path.resolve(fileUri.fsPath));
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`File must be inside server workspace root: ${workspaceRoot}`);
  }
  return relative.split(path.sep).join('/');
}

function selectionToEditorRange(selection: vscode.Selection): EditorRange | undefined {
  if (selection.isEmpty) {
    return undefined;
  }
  return {
    start: {
      line: selection.start.line,
      character: selection.start.character,
    },
    end: {
      line: selection.end.line,
      character: selection.end.character,
    },
  };
}

function getActiveEditorOrThrow(): vscode.TextEditor {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    throw new Error('Open a file in the editor first.');
  }
  return editor;
}

function showStructuredResult(output: vscode.OutputChannel, result: AppCommandResponse): void {
  output.show(true);
  output.appendLine(`> ${result.command}`);
  output.appendLine(`[action=${result.action}, confidence=${result.confidence}]`);
  output.appendLine(result.response);
  output.appendLine('');
}

function buildInlineRange(editor: vscode.TextEditor): vscode.Range {
  if (!editor.selection.isEmpty) {
    return new vscode.Range(editor.selection.start, editor.selection.end);
  }
  return editor.document.lineAt(editor.selection.active.line).range;
}

function panelHtml(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>aicode Chat</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      padding: 12px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    h3 { margin-bottom: 6px; }
    .meta {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
      opacity: 0.9;
      font-size: 12px;
    }
    .status {
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--vscode-panel-border);
    }
    .layout {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 12px;
    }
    .panel {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 10px;
      min-height: 220px;
    }
    #history {
      max-height: 48vh;
      overflow: auto;
    }
    #actionLog {
      max-height: 48vh;
      overflow: auto;
      font-size: 12px;
    }
    .entry, .log-entry {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      padding: 8px;
      margin-bottom: 8px;
    }
    .prompt { font-weight: 600; margin-bottom: 6px; white-space: pre-wrap; }
    .reply { white-space: pre-wrap; margin-bottom: 8px; }
    .entry-actions { display: flex; justify-content: flex-end; gap: 8px; }
    .row { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
    input {
      flex: 1;
      min-width: 220px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      padding: 8px;
      border-radius: 4px;
    }
    button {
      padding: 8px 12px;
      border: 1px solid var(--vscode-button-border, transparent);
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-radius: 4px;
      cursor: pointer;
    }
    #recent { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { font-size: 12px; padding: 4px 8px; }
    .log-kind {
      font-weight: 600;
      margin-right: 6px;
    }
    .timestamp {
      opacity: 0.7;
      margin-right: 6px;
    }
    @media (max-width: 860px) {
      .layout {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <h3>aicode Chat Panel</h3>
  <div class="meta">
    <span id="serverStatus" class="status">Server status unknown</span>
    <span>Managed local server, chat, editor actions, and action log.</span>
  </div>
  <div class="layout">
    <div class="panel">
      <strong>Chat</strong>
      <div id="history"></div>
      <div class="row">
        <input id="prompt" placeholder="e.g. status or please help build itself in 3 cycles" />
        <button id="send">Send</button>
      </div>
      <div class="row">
        <button id="health">Check API</button>
        <button id="restart">Restart Server</button>
        <button id="editFile">Edit File</button>
        <button id="editSelection">Edit Selection</button>
        <button id="inlineChat">Inline Chat</button>
      </div>
      <div id="recent"></div>
    </div>
    <div class="panel">
      <strong>Action Log</strong>
      <div id="actionLog"></div>
    </div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const history = document.getElementById('history');
    const recent = document.getElementById('recent');
    const actionLog = document.getElementById('actionLog');
    const input = document.getElementById('prompt');
    const send = document.getElementById('send');
    const health = document.getElementById('health');
    const restart = document.getElementById('restart');
    const editFile = document.getElementById('editFile');
    const editSelection = document.getElementById('editSelection');
    const inlineChat = document.getElementById('inlineChat');
    const serverStatus = document.getElementById('serverStatus');
    const state = vscode.getState() || { commands: [] };
    let commandHistory = Array.isArray(state.commands) ? state.commands : [];
    const activeEntries = new Map();

    function rememberCommand(command) {
      const next = [command, ...commandHistory.filter((item) => item !== command)];
      commandHistory = next.slice(0, 8);
      vscode.setState({ commands: commandHistory });
      renderRecent();
    }

    function renderRecent() {
      recent.innerHTML = '';
      for (const command of commandHistory) {
        const button = document.createElement('button');
        button.className = 'chip';
        button.textContent = 'Retry: ' + command;
        button.title = command;
        button.addEventListener('click', () => submit(command));
        recent.appendChild(button);
      }
    }

    function renderActionLog(entries) {
      actionLog.innerHTML = '';
      if (!Array.isArray(entries) || !entries.length) {
        const empty = document.createElement('div');
        empty.className = 'log-entry';
        empty.textContent = 'No actions yet.';
        actionLog.appendChild(empty);
        return;
      }
      for (const entry of entries) {
        const row = document.createElement('div');
        row.className = 'log-entry';

        const stamp = document.createElement('span');
        stamp.className = 'timestamp';
        stamp.textContent = new Date(entry.timestamp).toLocaleTimeString();

        const kind = document.createElement('span');
        kind.className = 'log-kind';
        kind.textContent = '[' + entry.kind + ']';

        const message = document.createElement('span');
        message.textContent = entry.message;

        row.appendChild(stamp);
        row.appendChild(kind);
        row.appendChild(message);
        actionLog.appendChild(row);
      }
    }

    function setServerStatus(status) {
      if (!status) {
        return;
      }
      serverStatus.textContent = status.detail || status.text || 'Server status unknown';
    }

    function ensureEntry(id, command) {
      if (activeEntries.has(id)) {
        return activeEntries.get(id);
      }

      const card = document.createElement('div');
      card.className = 'entry';

      const prompt = document.createElement('div');
      prompt.className = 'prompt';
      prompt.textContent = '> ' + command;

      const meta = document.createElement('div');
      meta.className = 'meta';

      const reply = document.createElement('div');
      reply.className = 'reply';
      reply.textContent = '';

      const actions = document.createElement('div');
      actions.className = 'entry-actions';
      const retry = document.createElement('button');
      retry.textContent = 'Retry';
      retry.addEventListener('click', () => submit(command));
      actions.appendChild(retry);

      card.appendChild(prompt);
      card.appendChild(meta);
      card.appendChild(reply);
      card.appendChild(actions);
      history.appendChild(card);
      history.scrollTop = history.scrollHeight;
      const entry = { card, meta, reply };
      activeEntries.set(id, entry);
      return entry;
    }

    function appendEntry(command, body) {
      const id = 'entry-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
      const entry = ensureEntry(id, command);
      entry.reply.textContent = body;
    }

    function setEntryMeta(id, command, text) {
      const entry = ensureEntry(id, command);
      entry.meta.textContent = text || '';
    }

    function setEntryBody(id, command, body) {
      const entry = ensureEntry(id, command);
      entry.reply.textContent = body;
      history.scrollTop = history.scrollHeight;
    }

    function appendToEntry(id, command, chunk) {
      const entry = ensureEntry(id, command);
      entry.reply.textContent += chunk;
      history.scrollTop = history.scrollHeight;
    }

    function submit(commandOverride) {
      const value = typeof commandOverride === 'string' ? commandOverride : input.value.trim();
      if (!value) {
        return;
      }
      rememberCommand(value);
      const requestId = 'req-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
      vscode.postMessage({ type: 'ask', command: value, requestId });
      if (!commandOverride) {
        input.value = '';
      }
      input.focus();
    }

    send.addEventListener('click', submit);
    health.addEventListener('click', () => vscode.postMessage({ type: 'health' }));
    restart.addEventListener('click', () => vscode.postMessage({ type: 'restartServer' }));
    editFile.addEventListener('click', () => vscode.postMessage({ type: 'editCurrentFile' }));
    editSelection.addEventListener('click', () => vscode.postMessage({ type: 'editSelection' }));
    inlineChat.addEventListener('click', () => vscode.postMessage({ type: 'inlineChat' }));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        submit();
      }
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (msg.type === 'init') {
        renderActionLog(msg.entries || []);
        setServerStatus(msg.status);
      }
      if (msg.type === 'result') {
        appendEntry(msg.command || 'unknown', '[action=' + msg.action + ', confidence=' + msg.confidence + ']\\n' + msg.response);
      }
      if (msg.type === 'error') {
        if (msg.requestId) {
          setEntryMeta(msg.requestId, msg.command || 'unknown', 'Request failed');
          setEntryBody(msg.requestId, msg.command || 'unknown', 'ERROR: ' + msg.message);
        } else {
          appendEntry(msg.command || 'unknown', 'ERROR: ' + msg.message);
        }
      }
      if (msg.type === 'health') {
        appendEntry('health', msg.message);
      }
      if (msg.type === 'streamStart') {
        ensureEntry(msg.requestId, msg.command || 'unknown');
        setEntryMeta(msg.requestId, msg.command || 'unknown', 'Routing request...');
      }
      if (msg.type === 'streamRoute') {
        setEntryMeta(
          msg.requestId,
          msg.command || 'unknown',
          '[action=' + msg.action + ', confidence=' + msg.confidence + ']',
        );
      }
      if (msg.type === 'streamDelta') {
        appendToEntry(msg.requestId, msg.command || 'unknown', msg.chunk || '');
      }
      if (msg.type === 'streamDone') {
        setEntryMeta(
          msg.requestId,
          msg.command || 'unknown',
          '[action=' + msg.action + ', confidence=' + msg.confidence + ']',
        );
        if (!msg.response) {
          setEntryBody(msg.requestId, msg.command || 'unknown', '(no response)');
        }
      }
      if (msg.type === 'actionLog') {
        renderActionLog(msg.entries || []);
      }
      if (msg.type === 'serverStatus') {
        setServerStatus(msg.status);
      }
    });

    renderRecent();
    vscode.postMessage({ type: 'ready' });
  </script>
</body>
</html>`;
}

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('aicode');
  const actionLog = new ActionLogStore(output);
  const serverManager = new ServerManager(context, output, actionLog);
  const commentController = vscode.comments.createCommentController('aicode-inline', 'aicode Inline');

  let panel: vscode.WebviewPanel | undefined;

  const postPanelMessage = (message: unknown): void => {
    if (panel) {
      void panel.webview.postMessage(message);
    }
  };

  const syncPanelState = (): void => {
    postPanelMessage({ type: 'init', entries: actionLog.getEntries(), status: serverManager.getStatus() });
  };

  const logServerEvents = (events: ActionEvent[] | undefined): void => {
    actionLog.appendMany(events, 'server');
  };

  const formatHealthSummary = (health: HealthResponse): string => {
    const ollama = normalizeOllamaHealth(health, health.base_url);
    const ollamaSummary = ollama.reachable
      ? `Ollama ready at ${health.base_url}`
      : `Ollama unavailable at ${health.base_url}: ${ollama.detail}`;
    return `Server ready at ${normalizeBaseUrl()} (${health.model}). ${ollamaSummary}`;
  };

  const callAppCommand = async (command: string): Promise<AppCommandResponse> => {
    await serverManager.ensureModelReady();
    actionLog.append('command', command, 'client');
    const result = await fetchJson<AppCommandResponse>(
      commandUrl(),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      },
      20000,
    );
    logServerEvents(result.events);
    return result;
  };

  const streamAppCommand = async (
    command: string,
    callbacks: StreamCallbacks = {},
  ): Promise<AppCommandResponse> => {
    await serverManager.ensureModelReady();
    actionLog.append('command', command, 'client');
    const response = await fetch(streamCommandUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    if (!response.body) {
      throw new Error('Streaming response body was not available.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let streamedResponse = '';
    let finalAction = 'unknown';
    let finalConfidence = 0;

    const handleEvent = (entry: StreamEvent): void => {
      const payload = entry.data;
      if (entry.event === 'route') {
        finalAction = String(payload.action ?? finalAction);
        finalConfidence = Number(payload.confidence ?? finalConfidence);
        callbacks.onRoute?.(payload);
        return;
      }
      if (entry.event === 'status') {
        const message = String(payload.message ?? 'Working...');
        actionLog.append('status', message, 'server');
        callbacks.onStatus?.(payload);
        return;
      }
      if (entry.event === 'event') {
        const kind = String(payload.kind ?? 'event');
        const message = String(payload.message ?? '');
        if (message) {
          actionLog.append(kind, message, 'server');
        }
        callbacks.onEvent?.(payload);
        return;
      }
      if (entry.event === 'result') {
        finalAction = String(payload.action ?? finalAction);
        finalConfidence = Number(payload.confidence ?? finalConfidence);
        callbacks.onResult?.(payload);
        return;
      }
      if (entry.event === 'delta') {
        const text = String(payload.text ?? '');
        streamedResponse += text;
        callbacks.onDelta?.(payload);
        return;
      }
      if (entry.event === 'done') {
        if (!streamedResponse && typeof payload.response === 'string') {
          streamedResponse = payload.response;
        }
        finalAction = String(payload.action ?? finalAction);
        finalConfidence = Number(payload.confidence ?? finalConfidence);
        callbacks.onDone?.(payload);
        return;
      }
      if (entry.event === 'error') {
        throw new Error(String(payload.message ?? 'Unknown streaming error'));
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? '';
      for (const block of blocks) {
        const entry = parseSseBlock(block);
        if (entry) {
          handleEvent(entry);
        }
      }
      if (done) {
        break;
      }
    }

    const trailing = parseSseBlock(buffer);
    if (trailing) {
      handleEvent(trailing);
    }

    return {
      command,
      action: finalAction,
      confidence: finalConfidence,
      response: streamedResponse,
    };
  };

  const callEditorChat = async (
    editor: vscode.TextEditor,
    prompt: string,
  ): Promise<EditorChatResponse> => {
    const health = await serverManager.ensureModelReady();
    const request: EditorChatRequest = {
      path: toServerRelativePath(editor.document.uri, health.workspace_root),
      prompt,
      current_content: editor.document.getText(),
      selection: selectionToEditorRange(editor.selection),
    };
    actionLog.append('chat', `Inline chat for ${request.path}`, 'client');
    const result = await fetchJson<EditorChatResponse>(
      editorChatUrl(),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      },
      30000,
    );
    logServerEvents(result.events);
    return result;
  };

  const callEditPreview = async (
    editor: vscode.TextEditor,
    instruction: string,
    selectionOnly: boolean,
  ): Promise<EditorEditPreviewResponse> => {
    const health = await serverManager.ensureModelReady();
    const selection = selectionOnly ? selectionToEditorRange(editor.selection) : undefined;
    if (selectionOnly && !selection) {
      throw new Error('Select code first, or use "aicode: Edit Current File".');
    }

    const request: EditorEditPreviewRequest = {
      path: toServerRelativePath(editor.document.uri, health.workspace_root),
      instruction,
      current_content: editor.document.getText(),
      selection,
    };
    actionLog.append(
      'edit',
      `Requesting ${selectionOnly ? 'selection' : 'file'} edit preview for ${request.path}`,
      'client',
    );
    const result = await fetchJson<EditorEditPreviewResponse>(
      editorPreviewUrl(),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      },
      45000,
    );
    logServerEvents(result.events);
    return result;
  };

  const applyUpdatedContent = async (
    editor: vscode.TextEditor,
    updatedContent: string,
  ): Promise<void> => {
    const fullRange = new vscode.Range(
      editor.document.positionAt(0),
      editor.document.positionAt(editor.document.getText().length),
    );
    const edit = new vscode.WorkspaceEdit();
    edit.replace(editor.document.uri, fullRange, updatedContent);
    const applied = await vscode.workspace.applyEdit(edit);
    if (!applied) {
      throw new Error('VS Code rejected the file update.');
    }
    actionLog.append('apply', `Applied changes to ${editor.document.fileName}`, 'client');
  };

  const openPreviewDiff = async (
    editor: vscode.TextEditor,
    preview: EditorEditPreviewResponse,
  ): Promise<boolean> => {
    const previewDoc = await vscode.workspace.openTextDocument({
      language: editor.document.languageId,
      content: preview.updated_content,
    });
    await vscode.commands.executeCommand(
      'vscode.diff',
      editor.document.uri,
      previewDoc.uri,
      `aicode Preview: ${path.basename(editor.document.uri.fsPath)}`,
    );
    actionLog.append('diff', `Opened diff preview for ${editor.document.fileName}`, 'client');
    const choice = await vscode.window.showInformationMessage(
      `aicode prepared a ${preview.mode} edit preview for ${path.basename(editor.document.fileName)}.`,
      'Apply',
      'Keep Preview',
    );
    return choice === 'Apply';
  };

  const createInlineThread = (
    editor: vscode.TextEditor,
    prompt: string,
    response: string,
  ): void => {
    const thread = commentController.createCommentThread(
      editor.document.uri,
      buildInlineRange(editor),
      [
        {
          body: new vscode.MarkdownString(prompt),
          mode: vscode.CommentMode.Preview,
          author: { name: 'You' },
        },
        {
          body: new vscode.MarkdownString(response),
          mode: vscode.CommentMode.Preview,
          author: { name: 'aicode' },
        },
      ],
    );
    thread.label = 'aicode inline chat';
    thread.collapsibleState = vscode.CommentThreadCollapsibleState.Expanded;
    thread.canReply = false;
    actionLog.append('chat', `Attached inline chat thread to ${editor.document.fileName}`, 'client');
  };

  actionLog.onDidChange((entries) => {
    postPanelMessage({ type: 'actionLog', entries });
  });

  serverManager.onDidChangeStatus((status) => {
    postPanelMessage({ type: 'serverStatus', status });
  });

  const askDisposable = vscode.commands.registerCommand('aicode.ask', async () => {
    const command = await vscode.window.showInputBox({
      prompt: 'Ask aicode',
      placeHolder: 'e.g. status or repo summary',
      ignoreFocusOut: true,
    });

    if (!command) {
      return;
    }

    try {
      const result = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'aicode is thinking…' },
        () => streamAppCommand(command),
      );
      showStructuredResult(output, result);
      postPanelMessage({
        type: 'result',
        command: result.command,
        action: result.action,
        confidence: result.confidence,
        response: result.response,
      });
      vscode.window.showInformationMessage(`aicode: ${result.action}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`aicode request failed (${commandUrl()}): ${message}`);
    }
  });

  const statusDisposable = vscode.commands.registerCommand('aicode.status', async () => {
    try {
      const health = await serverManager.ensureRunning();
      const message = formatHealthSummary(health);
      actionLog.append('health', message, 'extension');
      vscode.window.showInformationMessage(message);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showWarningMessage(`aicode API not reachable (${normalizeBaseUrl()}): ${message}`);
    }
  });

  const restartDisposable = vscode.commands.registerCommand('aicode.restartServer', async () => {
    try {
      const health = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Restarting aicode server…' },
        () => serverManager.restart(),
      );
      vscode.window.showInformationMessage(formatHealthSummary(health));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not restart aicode server: ${message}`);
    }
  });

  const showActionLogDisposable = vscode.commands.registerCommand('aicode.showActionLog', () => {
    output.show(true);
  });

  const editCurrentFileDisposable = vscode.commands.registerCommand(
    'aicode.editCurrentFile',
    async () => {
      const editor = getActiveEditorOrThrow();
      const instruction = await vscode.window.showInputBox({
        prompt: 'Describe the change you want in the current file',
        placeHolder: 'e.g. extract a helper and simplify this function',
        ignoreFocusOut: true,
      });
      if (!instruction) {
        return;
      }

      try {
        const preview = await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: 'Preparing file edit preview…' },
          () => callEditPreview(editor, instruction, false),
        );
        const apply = await openPreviewDiff(editor, preview);
        if (apply) {
          await applyUpdatedContent(editor, preview.updated_content);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        actionLog.append('error', message, 'extension');
        vscode.window.showErrorMessage(`aicode edit preview failed: ${message}`);
      }
    },
  );

  const editSelectionDisposable = vscode.commands.registerCommand(
    'aicode.editSelection',
    async () => {
      const editor = getActiveEditorOrThrow();
      if (editor.selection.isEmpty) {
        vscode.window.showWarningMessage('Select code first, or use "aicode: Edit Current File".');
        return;
      }

      const instruction = await vscode.window.showInputBox({
        prompt: 'Describe the change you want for the selected code',
        placeHolder: 'e.g. make this loop safer and easier to read',
        ignoreFocusOut: true,
      });
      if (!instruction) {
        return;
      }

      try {
        const preview = await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: 'Preparing selection edit preview…' },
          () => callEditPreview(editor, instruction, true),
        );
        const apply = await openPreviewDiff(editor, preview);
        if (apply) {
          await applyUpdatedContent(editor, preview.updated_content);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        actionLog.append('error', message, 'extension');
        vscode.window.showErrorMessage(`aicode selection edit failed: ${message}`);
      }
    },
  );

  const inlineChatDisposable = vscode.commands.registerCommand('aicode.inlineChat', async () => {
    const editor = getActiveEditorOrThrow();
    const prompt = await vscode.window.showInputBox({
      prompt: 'Ask aicode about the current file or selection',
      placeHolder: 'e.g. explain this function or suggest a safer approach',
      ignoreFocusOut: true,
    });
    if (!prompt) {
      return;
    }

    try {
      const result = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Creating inline chat…' },
        () => callEditorChat(editor, prompt),
      );
      createInlineThread(editor, prompt, result.response);
      vscode.window.showInformationMessage('aicode inline chat added to the editor.');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`aicode inline chat failed: ${message}`);
    }
  });

  const panelDisposable = vscode.commands.registerCommand('aicode.openPanel', async () => {
    if (panel) {
      panel.reveal(vscode.ViewColumn.Beside);
      syncPanelState();
      return;
    }

    panel = vscode.window.createWebviewPanel('aicodeChatPanel', 'aicode Chat', vscode.ViewColumn.Beside, {
      enableScripts: true,
    });
    panel.webview.html = panelHtml();

    panel.onDidDispose(() => {
      panel = undefined;
    });

    panel.webview.onDidReceiveMessage(async (message: unknown) => {
      const payload =
        typeof message === 'object' && message !== null
          ? (message as { type?: string; command?: unknown })
          : {};

      if (payload.type === 'ready') {
        syncPanelState();
        return;
      }

      if (payload.type === 'health') {
        try {
          const health = await serverManager.ensureRunning();
          postPanelMessage({
            type: 'health',
            message: formatHealthSummary(health),
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          postPanelMessage({ type: 'health', message: `API ERROR: ${text}` });
        }
        return;
      }

      if (payload.type === 'restartServer') {
        try {
          const health = await serverManager.restart();
          postPanelMessage({
            type: 'health',
            message: formatHealthSummary(health),
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          postPanelMessage({ type: 'error', command: 'restart', message: text });
        }
        return;
      }

      if (payload.type === 'editCurrentFile') {
        await vscode.commands.executeCommand('aicode.editCurrentFile');
        return;
      }

      if (payload.type === 'editSelection') {
        await vscode.commands.executeCommand('aicode.editSelection');
        return;
      }

      if (payload.type === 'inlineChat') {
        await vscode.commands.executeCommand('aicode.inlineChat');
        return;
      }

      if (payload.type !== 'ask') {
        return;
      }

      const command = String(payload.command ?? '').trim();
      const requestId = String((payload as { requestId?: unknown }).requestId ?? '');
      if (!command) {
        return;
      }

      try {
        postPanelMessage({ type: 'streamStart', requestId, command });
        await streamAppCommand(command, {
          onRoute: (entry) => {
            postPanelMessage({
              type: 'streamRoute',
              requestId,
              command,
              action: String(entry.action ?? 'unknown'),
              confidence: Number(entry.confidence ?? 0),
            });
          },
          onDelta: (entry) => {
            postPanelMessage({
              type: 'streamDelta',
              requestId,
              command,
              chunk: String(entry.text ?? ''),
            });
          },
          onDone: (entry) => {
            postPanelMessage({
              type: 'streamDone',
              requestId,
              command,
              action: String(entry.action ?? 'unknown'),
              confidence: Number(entry.confidence ?? 0),
              response: String(entry.response ?? ''),
            });
          },
        });
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        postPanelMessage({ type: 'error', requestId, command, message: text });
      }
    });

    syncPanelState();
  });

  context.subscriptions.push(
    askDisposable,
    statusDisposable,
    restartDisposable,
    showActionLogDisposable,
    editCurrentFileDisposable,
    editSelectionDisposable,
    inlineChatDisposable,
    panelDisposable,
    output,
    actionLog,
    serverManager,
    commentController,
  );

  if (serverManager.autoStartEnabled()) {
    void serverManager.ensureRunning().catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('health', `Auto-start failed: ${message}`, 'extension');
    });
  }
}

export function deactivate() {}
