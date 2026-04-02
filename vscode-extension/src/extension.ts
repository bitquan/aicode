import { ChildProcess, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

import * as vscode from 'vscode';
import {
  buildOllamaGuidance,
  compareWorkspaceBuilds,
  describeWorkspaceBuildMissing,
  detectExtensionRuntimeMode,
  describeRuntimeMismatch,
  discoverServerRoot,
  discoverWorkspaceExtensionRoot,
  formatExtensionBuildSummary,
  formatHealthSummaryMessage,
  formatRuntimeStatusLabel,
  formatServerRuntimeSummary,
  isValidServerRoot,
  loadExtensionBuildInfo,
  loadRuntimeManifest,
  looksLikeEditInstruction,
  normalizeOllamaHealth,
  shouldFallbackToNonStreaming,
  validateExtensionBuildInfo,
  type ExtensionBuildInfo,
  type ExtensionBuildSnapshot,
  type OllamaHealth,
  type RuntimeMetadata,
  type WorkspaceBuildComparison,
} from './runtime_support';

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
  next_step?: string;
  events?: ActionEvent[];
};

type HealthResponse = {
  status: string;
  workspace_root: string;
  model: string;
  base_url: string;
  ollama: OllamaHealth;
  runtime?: RuntimeMetadata;
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

type InlineSuggestion = {
  id: string;
  uri: vscode.Uri;
  updatedContent: string;
  mode: string;
  prompt: string;
};

// ---------------------------------------------------------------------------
// Terminal capture
// ---------------------------------------------------------------------------

type CapturedCommand = {
  id: string;
  command: string;
  exitCode?: number;
  cwd?: string;
  timestamp: string;
};

const MAX_CAPTURED_COMMANDS = 30;
const capturedTerminalCommands: CapturedCommand[] = [];

function addCapturedCommand(cmd: Omit<CapturedCommand, 'id'>): void {
  capturedTerminalCommands.unshift({ id: `cap-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, ...cmd });
  if (capturedTerminalCommands.length > MAX_CAPTURED_COMMANDS) {
    capturedTerminalCommands.length = MAX_CAPTURED_COMMANDS;
  }
}

// ---------------------------------------------------------------------------
// Diagnostics helper
// ---------------------------------------------------------------------------

function diagSeverityLabel(s: vscode.DiagnosticSeverity | undefined): string {
  switch (s) {
    case vscode.DiagnosticSeverity.Error: return 'error';
    case vscode.DiagnosticSeverity.Warning: return 'warning';
    case vscode.DiagnosticSeverity.Information: return 'info';
    case vscode.DiagnosticSeverity.Hint: return 'hint';
    default: return 'problem';
  }
}

// ---------------------------------------------------------------------------
// Git helper (vscode.git extension)
// ---------------------------------------------------------------------------

type GitApi = {
  repositories: Array<{
    inputBox: { value: string };
    state: {
      workingTreeChanges: Array<{ uri: vscode.Uri; status: number }>;
      indexChanges: Array<{ uri: vscode.Uri; status: number }>;
    };
    diff(staged: boolean): Promise<string>;
  }>;
};

async function getGitApi(): Promise<GitApi | undefined> {
  const ext = vscode.extensions.getExtension<{ getAPI(v: number): GitApi }>('vscode.git');
  if (!ext) return undefined;
  if (!ext.isActive) await ext.activate();
  return ext.exports.getAPI(1);
}

type ServerStatusSnapshot = {
  text: string;
  detail: string;
  healthy: boolean;
  extensionBuild?: ExtensionBuildInfo;
  workspaceBuildComparison?: WorkspaceBuildComparison;
  integrityIssue?: string;
  serverRuntime?: RuntimeMetadata;
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

const WORKSPACE_TASK_LABELS = {
  server: 'run:aicode-server',
  ollama: 'run:ollama-serve',
  tests: 'test:aicode-all',
  buildExtension: 'build:vscode-extension',
} as const;

function getConfiguration(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration('aicode');
}

function shouldStopManagedServerOnDeactivate(): boolean {
  return Boolean(getConfiguration().get('stopServerOnDeactivate', true));
}

function shouldAutoStartOllama(): boolean {
  return Boolean(getConfiguration().get('autoStartOllama', true));
}

function shouldUseIntegratedTerminal(): boolean {
  return Boolean(getConfiguration().get('showManagedProcessesInTerminal', true));
}

function preferWorkspaceTasks(): boolean {
  return Boolean(getConfiguration().get('preferWorkspaceTasks', true));
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

class SidebarQuickActionsProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    const openPanel = new vscode.TreeItem('Open Chat Panel', vscode.TreeItemCollapsibleState.None);
    openPanel.command = { command: 'aicode.openPanel', title: 'Open Chat Panel' };
    openPanel.description = 'Primary workspace';
    openPanel.iconPath = new vscode.ThemeIcon('comment-discussion');

    const ask = new vscode.TreeItem('Ask Aicode', vscode.TreeItemCollapsibleState.None);
    ask.command = { command: 'aicode.ask', title: 'Ask Aicode' };
    ask.description = 'Quick command';
    ask.iconPath = new vscode.ThemeIcon('send');

    const status = new vscode.TreeItem('Check Runtime Status', vscode.TreeItemCollapsibleState.None);
    status.command = { command: 'aicode.status', title: 'Check Runtime Status' };
    status.description = 'Server + model health';
    status.iconPath = new vscode.ThemeIcon('pulse');

    const restart = new vscode.TreeItem('Restart Local Server', vscode.TreeItemCollapsibleState.None);
    restart.command = { command: 'aicode.restartServer', title: 'Restart Local Server' };
    restart.description = 'Managed process';
    restart.iconPath = new vscode.ThemeIcon('debug-restart');

    const runTask = new vscode.TreeItem('Run VS Code Task', vscode.TreeItemCollapsibleState.None);
    runTask.command = { command: 'aicode.runWorkspaceTask', title: 'Run VS Code Task' };
    runTask.description = 'Workspace task picker';
    runTask.iconPath = new vscode.ThemeIcon('tools');

    return [openPanel, ask, status, restart, runTask];
  }
}

class BuildRuntimeInspector {
  constructor(private readonly context: vscode.ExtensionContext) {}

  private workspaceFolderPaths(): string[] {
    return (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath);
  }

  workspaceExtensionRoot(): string | undefined {
    return discoverWorkspaceExtensionRoot(this.workspaceFolderPaths());
  }

  snapshot(): ExtensionBuildSnapshot {
    const workspaceExtensionRoot = this.workspaceExtensionRoot();
    const runtimeMode = detectExtensionRuntimeMode(this.context.extensionPath, workspaceExtensionRoot);
    const loaded = loadExtensionBuildInfo(this.context.extensionPath, runtimeMode);
    const workspace = workspaceExtensionRoot
      ? loadExtensionBuildInfo(workspaceExtensionRoot, 'workspace')
      : undefined;
    const integrityIssue = validateExtensionBuildInfo(this.context.extensionPath, loaded);

    let workspaceBuildComparison: WorkspaceBuildComparison | undefined;
    if (runtimeMode === 'development-host' && loaded) {
      workspaceBuildComparison = compareWorkspaceBuilds(loaded, workspace ?? loaded);
    } else if (workspaceExtensionRoot) {
      workspaceBuildComparison = workspace
        ? compareWorkspaceBuilds(loaded, workspace)
        : describeWorkspaceBuildMissing();
    }

    return {
      extensionBuild: loaded,
      workspaceBuildComparison,
      integrityIssue,
    };
  }
}

class ServerManager implements vscode.Disposable {
  private child: ChildProcess | undefined;
  private startedByExtension = false;
  private ollamaChild: ChildProcess | undefined;
  private startedOllamaByExtension = false;
  private serverTaskExecution: vscode.TaskExecution | undefined;
  private ollamaTaskExecution: vscode.TaskExecution | undefined;
  private serverTerminal: vscode.Terminal | undefined;
  private ollamaTerminal: vscode.Terminal | undefined;
  private readonly statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  private readonly emitter = new vscode.EventEmitter<ServerStatusSnapshot>();
  private readonly healthTimer: ReturnType<typeof setInterval>;
  private readonly taskDisposables: vscode.Disposable[] = [];
  private lastOutputLines: string[] = [];
  private lastExitDetail = 'No server process launched yet.';
  private lastOllamaExitDetail = 'No Ollama process launched yet.';
  private lastHealth: HealthResponse | undefined;
  private lastRuntimeMismatch = '';
  private lastBuildComparisonDetail = '';
  private lastBuildIntegrityIssue = '';
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
    private readonly buildInspector: BuildRuntimeInspector,
  ) {
    this.statusBar.command = 'aicode.status';
    this.statusBar.tooltip = this.status.detail;
    this.statusBar.text = this.status.text;
    this.statusBar.show();
    this.status = this.buildStatusSnapshot(this.status.text, this.status.detail, this.status.healthy);
    this.statusBar.tooltip = this.status.detail;

    this.healthTimer = setInterval(() => {
      void this.refreshHealth(false);
    }, 15000);

    this.taskDisposables.push(
      vscode.tasks.onDidEndTaskProcess((event) => {
        if (this.serverTaskExecution && event.execution === this.serverTaskExecution) {
          const detail = `Server task ended${typeof event.exitCode === 'number' ? ` with code ${event.exitCode}` : ''}`;
          this.lastExitDetail = detail;
          this.actionLog.append('server', detail, 'extension');
          this.serverTaskExecution = undefined;
          if (!(this.child && this.child.exitCode === null) && !this.serverTerminal) {
            this.startedByExtension = false;
            this.updateStatus('$(warning) aicode', detail, false);
          }
        }
        if (this.ollamaTaskExecution && event.execution === this.ollamaTaskExecution) {
          const detail = `Ollama task ended${typeof event.exitCode === 'number' ? ` with code ${event.exitCode}` : ''}`;
          this.lastOllamaExitDetail = detail;
          this.actionLog.append('ollama', detail, 'extension');
          this.ollamaTaskExecution = undefined;
          if (!(this.ollamaChild && this.ollamaChild.exitCode === null) && !this.ollamaTerminal) {
            this.startedOllamaByExtension = false;
          }
        }
      }),
      vscode.tasks.onDidEndTask((event) => {
        if (this.serverTaskExecution && event.execution === this.serverTaskExecution) {
          this.serverTaskExecution = undefined;
        }
        if (this.ollamaTaskExecution && event.execution === this.ollamaTaskExecution) {
          this.ollamaTaskExecution = undefined;
        }
      }),
    );
  }

  baseUrl(): string {
    return normalizeBaseUrl();
  }

  serverRoot(): string {
    return this.resolveServerRoot();
  }

  autoStartEnabled(): boolean {
    return Boolean(getConfiguration().get('autoStartServer', true));
  }

  autoStartOllamaEnabled(): boolean {
    return shouldAutoStartOllama();
  }

  isManagedServerRunning(): boolean {
    return Boolean(
      this.startedByExtension
      && ((this.child && this.child.exitCode === null) || this.serverTerminal || this.serverTaskExecution),
    );
  }

  isManagedOllamaRunning(): boolean {
    return Boolean(
      this.startedOllamaByExtension
      && ((this.ollamaChild && this.ollamaChild.exitCode === null) || this.ollamaTerminal || this.ollamaTaskExecution),
    );
  }

  handleTerminalClosed(terminal: vscode.Terminal): void {
    if (this.serverTerminal && terminal === this.serverTerminal) {
      this.serverTerminal = undefined;
      if (this.startedByExtension && !(this.child && this.child.exitCode === null)) {
        this.lastExitDetail = 'Server terminal closed.';
        this.startedByExtension = false;
      }
    }
    if (this.ollamaTerminal && terminal === this.ollamaTerminal) {
      this.ollamaTerminal = undefined;
      if (this.startedOllamaByExtension && !(this.ollamaChild && this.ollamaChild.exitCode === null)) {
        this.lastOllamaExitDetail = 'Ollama terminal closed.';
        this.startedOllamaByExtension = false;
      }
    }
  }

  getStatus(): ServerStatusSnapshot {
    return { ...this.status };
  }

  getBuildSnapshot(): ExtensionBuildSnapshot {
    return this.buildInspector.snapshot();
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
    let ollama = normalizeOllamaHealth(health, health.base_url);
    if (!ollama.reachable && this.autoStartOllamaEnabled()) {
      await this.startOllamaServe(health.base_url);
      ollama = await this.waitForOllamaReady(health.base_url, 20000);
      const refreshed = await this.refreshHealth(false);
      if (refreshed) {
        return refreshed;
      }
    }
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

  async start(): Promise<HealthResponse> {
    const healthy = await this.refreshHealth(false);
    if (healthy) {
      return healthy;
    }
    await this.startServer();
    return this.waitForHealthy();
  }

  async stop(): Promise<void> {
    await this.shutdownManagedServer('Stopped from aicode command');
  }

  async startOllama(): Promise<OllamaHealth> {
    const baseUrl = this.lastHealth?.base_url ?? defaultOllamaBaseUrl();
    await this.startOllamaServe(baseUrl);
    return this.waitForOllamaReady(baseUrl, 20000);
  }

  async stopOllama(): Promise<void> {
    if (this.isManagedOllamaRunning()) {
      this.actionLog.append('ollama', 'Stopping managed Ollama', 'extension');
      await this.stopManagedOllamaProcess();
      this.startedOllamaByExtension = false;
    }
  }

  private configBaseDir(): string {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? this.context.extensionPath;
  }

  private workspaceFolderPaths(): string[] {
    return (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath);
  }

  private detectServerRoot(): string | undefined {
    return discoverServerRoot(this.workspaceFolderPaths(), this.context.extensionPath);
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

  private resolveOllamaPath(): string {
    const configured = String(getConfiguration().get('ollamaPath', '')).trim();
    if (!configured) {
      return process.platform === 'darwin' ? '/opt/homebrew/bin/ollama' : 'ollama';
    }
    return path.isAbsolute(configured) ? configured : path.resolve(this.configBaseDir(), configured);
  }

  private async findTaskByLabel(label: string): Promise<vscode.Task | undefined> {
    const tasks = await vscode.tasks.fetchTasks();
    return tasks.find((task) => task.name === label) ?? tasks.find((task) => task.definition?.label === label);
  }

  private async executeWorkspaceTask(
    label: string,
    kind: 'server' | 'ollama' | 'task',
  ): Promise<vscode.TaskExecution | undefined> {
    if (!preferWorkspaceTasks()) {
      return undefined;
    }
    const task = await this.findTaskByLabel(label);
    if (!task) {
      return undefined;
    }
    const execution = await vscode.tasks.executeTask(task);
    if (kind === 'server') {
      this.serverTaskExecution = execution;
      this.startedByExtension = true;
      this.lastExitDetail = `Server task running: ${label}`;
      this.actionLog.append('server', `Started workspace task ${label}`, 'extension');
      this.updateStatus('$(sync~spin) aicode', `Starting local server via VS Code task ${label}`, false);
    } else if (kind === 'ollama') {
      this.ollamaTaskExecution = execution;
      this.startedOllamaByExtension = true;
      this.lastOllamaExitDetail = `Ollama task running: ${label}`;
      this.actionLog.append('ollama', `Started workspace task ${label}`, 'extension');
    } else {
      this.actionLog.append('task', `Started workspace task ${label}`, 'extension');
    }
    return execution;
  }

  async runWorkspaceTask(label?: string): Promise<void> {
    const tasks = await vscode.tasks.fetchTasks();
    const candidates = tasks
      .filter((task) => Boolean(task.name))
      .sort((left, right) => left.name.localeCompare(right.name));

    if (!candidates.length) {
      throw new Error('No VS Code workspace tasks were found.');
    }

    let selectedLabel = label;
    if (!selectedLabel) {
      const picked = await vscode.window.showQuickPick(
        candidates.map((task) => ({
          label: task.name,
          description: String(task.source ?? 'workspace'),
        })),
        {
          placeHolder: 'Choose a VS Code task for aicode to run',
          ignoreFocusOut: true,
        },
      );
      if (!picked) {
        return;
      }
      selectedLabel = picked.label;
    }

    const kind: 'server' | 'ollama' | 'task' =
      selectedLabel === WORKSPACE_TASK_LABELS.server
        ? 'server'
        : selectedLabel === WORKSPACE_TASK_LABELS.ollama
          ? 'ollama'
          : 'task';
    const execution = await this.executeWorkspaceTask(selectedLabel, kind);
    if (!execution) {
      throw new Error(`VS Code task not found: ${selectedLabel}`);
    }
  }

  private updateStatus(text: string, detail: string, healthy: boolean): void {
    this.status = this.buildStatusSnapshot(text, detail, healthy, this.lastHealth?.runtime);
    this.statusBar.text = this.status.text;
    this.statusBar.tooltip = this.status.detail;
    this.statusBar.backgroundColor = this.status.healthy
      ? undefined
      : new vscode.ThemeColor('statusBarItem.warningBackground');
    this.emitter.fire(this.getStatus());
  }

  private buildStatusSnapshot(
    text: string,
    detail: string,
    healthy: boolean,
    serverRuntime?: RuntimeMetadata,
  ): ServerStatusSnapshot {
    const buildSnapshot = this.getBuildSnapshot();
    return {
      text,
      detail,
      healthy,
      extensionBuild: buildSnapshot.extensionBuild,
      workspaceBuildComparison: buildSnapshot.workspaceBuildComparison,
      integrityIssue: buildSnapshot.integrityIssue,
      serverRuntime,
    };
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
    const buildSnapshot = this.getBuildSnapshot();
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
      `Ollama launch command: ${this.resolveOllamaPath()} serve`,
      `Last Ollama process exit: ${this.lastOllamaExitDetail}`,
      `Ollama URL: ${ollamaBase}`,
      `Ollama status: ${ollama.reachable ? 'reachable' : 'unreachable'} (${ollama.detail})`,
      formatExtensionBuildSummary(buildSnapshot.extensionBuild),
    ];
    const runtimeMismatch = this.runtimeMismatch(this.lastHealth);
    if (this.lastHealth?.runtime) {
      lines.push(
        `Server runtime: app=${this.lastHealth.runtime.app_version} routing=${this.lastHealth.runtime.routing_generation} started=${this.lastHealth.runtime.started_at ?? 'unknown'}`,
      );
    }
    if (buildSnapshot.workspaceBuildComparison?.detail) {
      lines.push(buildSnapshot.workspaceBuildComparison.detail);
    }
    if (buildSnapshot.integrityIssue) {
      lines.push(`Extension integrity: ${buildSnapshot.integrityIssue}`);
    }
    if (runtimeMismatch) {
      lines.push(runtimeMismatch);
    }
    if (!ollama.reachable) {
      lines.push(buildOllamaGuidance(ollamaBase));
    }
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

  private runtimeMismatch(health: HealthResponse | undefined): string | undefined {
    const expected = loadRuntimeManifest(this.resolveServerRoot());
    return describeRuntimeMismatch(expected, health?.runtime);
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
        runtime:
          rawHealth.runtime && typeof rawHealth.runtime === 'object'
            ? (rawHealth.runtime as RuntimeMetadata)
            : undefined,
        ollama:
          rawHealth.ollama && typeof rawHealth.ollama === 'object'
            ? normalizeOllamaHealth(rawHealth as HealthResponse, String(rawHealth.base_url ?? defaultOllamaBaseUrl()))
            : await checkOllamaHealth(String(rawHealth.base_url ?? defaultOllamaBaseUrl())),
      };
      this.lastHealth = health;
      const ollamaDetail = health.ollama.reachable
        ? `Ollama ready (${health.model})`
        : `Ollama unavailable (${health.ollama.detail}). ${buildOllamaGuidance(health.base_url)}`;
      const runtimeMismatch = this.runtimeMismatch(health);
      const buildSnapshot = this.getBuildSnapshot();
      if (runtimeMismatch && runtimeMismatch !== this.lastRuntimeMismatch) {
        this.actionLog.append('runtime', runtimeMismatch, 'extension');
      }
      if (
        buildSnapshot.workspaceBuildComparison?.state === 'stale-install'
        && buildSnapshot.workspaceBuildComparison.detail !== this.lastBuildComparisonDetail
      ) {
        this.actionLog.append('build', buildSnapshot.workspaceBuildComparison.detail, 'extension');
      }
      if (
        buildSnapshot.integrityIssue
        && buildSnapshot.integrityIssue !== this.lastBuildIntegrityIssue
      ) {
        this.actionLog.append('build', buildSnapshot.integrityIssue, 'extension');
      }
      this.lastBuildComparisonDetail = buildSnapshot.workspaceBuildComparison?.detail ?? '';
      this.lastBuildIntegrityIssue = buildSnapshot.integrityIssue ?? '';
      this.lastRuntimeMismatch = runtimeMismatch || '';
      const overallHealthy = Boolean(
        health.ollama.reachable
        && !runtimeMismatch
        && !buildSnapshot.integrityIssue
        && buildSnapshot.workspaceBuildComparison?.state !== 'stale-install',
      );
      this.updateStatus(
        overallHealthy ? '$(check) aicode' : '$(warning) aicode',
        runtimeMismatch
          ? `${runtimeMismatch} ${ollamaDetail}`
          : formatHealthSummaryMessage(health, this.baseUrl()),
        overallHealthy,
      );
      return health;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.lastHealth = undefined;
      this.lastRuntimeMismatch = '';
      this.lastBuildComparisonDetail = '';
      this.lastBuildIntegrityIssue = '';
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
    if (this.serverTaskExecution) {
      return;
    }
    if (this.serverTerminal) {
      this.serverTerminal.show(true);
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

    const taskExecution = await this.executeWorkspaceTask(WORKSPACE_TASK_LABELS.server, 'server');
    if (taskExecution) {
      return;
    }

    if (shouldUseIntegratedTerminal()) {
      const terminal = vscode.window.createTerminal({
        name: 'aicode server',
        cwd: serverRoot,
        env: {
          ...process.env,
          WORKSPACE_ROOT: workspaceRoot,
          PYTHONUNBUFFERED: '1',
        },
      });
      this.serverTerminal = terminal;
      this.startedByExtension = true;
      this.lastExitDetail = 'Server running in integrated terminal.';
      terminal.show(true);
      terminal.sendText(`"${pythonPath}" -m src.server`, true);
      return;
    }

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

  private async startOllamaServe(baseUrl: string): Promise<void> {
    const probe = await checkOllamaHealth(baseUrl, 1000);
    if (probe.reachable) {
      this.actionLog.append('ollama', `Ollama already reachable at ${baseUrl}`, 'extension');
      return;
    }
    if (this.ollamaChild && this.ollamaChild.exitCode === null) {
      return;
    }
    if (this.ollamaTaskExecution) {
      return;
    }
    if (this.ollamaTerminal) {
      this.ollamaTerminal.show(true);
      return;
    }

    const ollamaPath = this.resolveOllamaPath();
    this.actionLog.append('ollama', `Starting Ollama: ${ollamaPath} serve`, 'extension');
    const taskExecution = await this.executeWorkspaceTask(WORKSPACE_TASK_LABELS.ollama, 'ollama');
    if (taskExecution) {
      return;
    }
    if (shouldUseIntegratedTerminal()) {
      const terminal = vscode.window.createTerminal({
        name: 'aicode ollama',
        cwd: this.resolveServerRoot(),
        env: {
          ...process.env,
        },
      });
      this.ollamaTerminal = terminal;
      this.startedOllamaByExtension = true;
      this.lastOllamaExitDetail = 'Ollama running in integrated terminal.';
      terminal.show(true);
      terminal.sendText(`"${ollamaPath}" serve`, true);
      return;
    }

    const child = spawn(ollamaPath, ['serve'], {
      cwd: this.resolveServerRoot(),
      env: {
        ...process.env,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    child.stdout?.on('data', (chunk: Buffer | string) => {
      this.rememberOutput('stdout', chunk);
      this.output.append(String(chunk));
    });
    child.stderr?.on('data', (chunk: Buffer | string) => {
      this.rememberOutput('stderr', chunk);
      this.output.append(String(chunk));
    });
    child.on('error', (error) => {
      this.lastOllamaExitDetail = `Spawn error: ${error.message}`;
      this.actionLog.append('ollama', `Failed to start Ollama: ${error.message}`, 'extension');
    });
    child.on('exit', (code, signal) => {
      this.ollamaChild = undefined;
      const detail = `Ollama exited${code !== null ? ` with code ${code}` : ''}${signal ? ` (${signal})` : ''}`;
      this.lastOllamaExitDetail = detail;
      this.actionLog.append('ollama', detail, 'extension');
      this.startedOllamaByExtension = false;
    });

    this.ollamaChild = child;
    this.startedOllamaByExtension = true;
    this.lastOllamaExitDetail = 'Ollama launch in progress.';
  }

  private async waitForOllamaReady(baseUrl: string, timeoutMs: number): Promise<OllamaHealth> {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const health = await checkOllamaHealth(baseUrl, 1000);
      if (health.reachable) {
        this.actionLog.append('ollama', `Ollama is ready at ${baseUrl}`, 'extension');
        return health;
      }
      await sleep(500);
    }
    return await checkOllamaHealth(baseUrl, 1000);
  }

  private async stopManagedProcess(): Promise<void> {
    if (this.serverTaskExecution) {
      const execution = this.serverTaskExecution;
      this.serverTaskExecution = undefined;
      execution.terminate();
      return;
    }
    if (this.serverTerminal) {
      this.serverTerminal.dispose();
      this.serverTerminal = undefined;
      this.child = undefined;
      return;
    }
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

  async shutdownManagedServer(reason = 'Workspace closed'): Promise<void> {
    if (this.isManagedServerRunning()) {
      this.actionLog.append('server', `Stopping managed server: ${reason}`, 'extension');
      await this.stopManagedProcess();
      this.startedByExtension = false;
      this.updateStatus('$(circle-large-outline) aicode', `Server stopped (${reason})`, false);
    }
    if (this.isManagedOllamaRunning()) {
      this.actionLog.append('ollama', `Stopping managed Ollama: ${reason}`, 'extension');
      await this.stopManagedOllamaProcess();
      this.startedOllamaByExtension = false;
    }
  }

  private async stopManagedOllamaProcess(): Promise<void> {
    if (this.ollamaTaskExecution) {
      const execution = this.ollamaTaskExecution;
      this.ollamaTaskExecution = undefined;
      execution.terminate();
      return;
    }
    if (this.ollamaTerminal) {
      this.ollamaTerminal.dispose();
      this.ollamaTerminal = undefined;
      this.ollamaChild = undefined;
      return;
    }
    if (!this.ollamaChild || this.ollamaChild.exitCode !== null) {
      this.ollamaChild = undefined;
      return;
    }

    const child = this.ollamaChild;
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, 3000);
      child.once('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
      child.kill();
    });
    this.ollamaChild = undefined;
  }

  private async waitForHealthy(): Promise<HealthResponse> {
    const startedAt = Date.now();
    while (Date.now() - startedAt < 30000) {
      const health = await this.refreshHealth(false);
      if (health) {
        return health;
      }
      if (!this.autoStartEnabled()) {
        throw new Error(await this.buildDiagnosticsMessage('Auto-start disabled while waiting for server readiness.'));
      }
      await sleep(500);
    }
    throw new Error(await this.buildDiagnosticsMessage(`Timed out waiting for aicode server at ${this.baseUrl()}.`));
  }

  dispose(): void {
    clearInterval(this.healthTimer);
    for (const disposable of this.taskDisposables) {
      disposable.dispose();
    }
    this.statusBar.dispose();
    this.emitter.dispose();
    if (this.serverTerminal) {
      this.serverTerminal.dispose();
      this.serverTerminal = undefined;
    }
    if (this.startedByExtension && this.child && this.child.exitCode === null) {
      this.child.kill();
    }
    if (this.ollamaTerminal) {
      this.ollamaTerminal.dispose();
      this.ollamaTerminal = undefined;
    }
    if (this.startedOllamaByExtension && this.ollamaChild && this.ollamaChild.exitCode === null) {
      this.ollamaChild.kill();
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

function buildInlineSuggestionLink(suggestionId: string): string {
  const args = encodeURIComponent(JSON.stringify([suggestionId]));
  return `command:aicode.applyInlineSuggestion?${args}`;
}

function buildAssistantComment(response: string, suggestionId?: string): vscode.MarkdownString {
  const body = suggestionId
    ? `${response}\n\n[Apply suggestion](${buildInlineSuggestionLink(suggestionId)})`
    : response;
  const markdown = new vscode.MarkdownString(body);
  markdown.isTrusted = Boolean(suggestionId);
  markdown.supportHtml = false;
  return markdown;
}

function runtimeMismatchForHealth(serverRoot: string, health: HealthResponse | undefined): string | undefined {
  const expected = loadRuntimeManifest(serverRoot);
  return describeRuntimeMismatch(expected, health?.runtime);
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
      padding: 10px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    h3 {
      margin: 0 0 8px 0;
      font-size: 13px;
      opacity: 0.9;
    }
    .app-shell {
      display: grid;
      gap: 10px;
    }
    .top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
      border: 1px solid var(--vscode-panel-border);
      border-radius: 10px;
      padding: 10px;
      background: var(--vscode-sideBar-background);
    }
    .top-status {
      display: grid;
      gap: 4px;
    }
    .top-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .top-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .top-actions > button {
      opacity: 0.8;
    }
    .top-actions > button:hover {
      opacity: 1;
    }
    .status-text {
      opacity: 0.9;
      font-size: 12px;
    }
    .status-hint {
      opacity: 0.76;
      font-size: 11px;
    }
    .status {
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--vscode-panel-border);
      font-size: 12px;
      font-weight: 600;
    }
    .status.ok {
      border-color: var(--vscode-testing-iconPassed);
      color: var(--vscode-testing-iconPassed);
    }
    .status.warn {
      border-color: var(--vscode-testing-iconFailed);
      color: var(--vscode-testing-iconFailed);
    }
    .primary {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-color: var(--vscode-button-border, transparent);
    }
    .layout-middle {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(240px, 1fr);
      gap: 8px;
    }
    .panel {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 10px;
      padding: 8px;
      background: var(--vscode-editor-background);
    }
    .panel-title {
      font-weight: 600;
      margin-bottom: 6px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      opacity: 0.82;
    }
    .composer-panel {
      padding: 12px;
      border-radius: 12px;
    }
    .composer-subtitle {
      font-size: 12px;
      opacity: 0.8;
      margin-bottom: 8px;
    }
    .runtime-menu > summary,
    details > summary {
      cursor: pointer;
      font-weight: 600;
      font-size: 12px;
    }
    .runtime-menu {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 2px 8px;
    }
    #serverStatus {
      margin-top: 8px;
      white-space: pre-wrap;
      font-size: 12px;
      opacity: 0.9;
    }
    #buildStatus {
      margin-top: 6px;
      white-space: pre-wrap;
      font-size: 12px;
      opacity: 0.9;
    }
    .task-shell {
      min-height: 208px;
    }
    .task-empty {
      border: 1px dashed var(--vscode-panel-border);
      border-radius: 8px;
      padding: 16px 12px;
      opacity: 0.84;
      font-size: 12px;
      text-align: center;
      line-height: 1.45;
      background: var(--vscode-sideBar-background);
    }
    #history {
      max-height: 40vh;
      overflow: auto;
    }
    #actionLog {
      max-height: 200px;
      overflow: auto;
      font-size: 12px;
    }
    .task-card,
    .log-entry {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 8px;
      margin-bottom: 6px;
      background: var(--vscode-editor-background);
    }
    .task-header {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 10px;
      margin-bottom: 8px;
    }
    .task-title {
      font-weight: 600;
      white-space: pre-wrap;
      margin-bottom: 4px;
      line-height: 1.35;
    }
    .task-status {
      font-size: 12px;
      opacity: 0.78;
    }
    .task-confidence {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
      opacity: 0.82;
    }
    .task-route {
      font-size: 11px;
      margin-bottom: 6px;
      opacity: 0.56;
      word-break: break-word;
    }
    .reply {
      white-space: pre-wrap;
      margin-bottom: 6px;
      font-size: 12px;
      line-height: 1.45;
    }
    .next-step {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 12px;
      background: var(--vscode-sideBar-background);
      margin-bottom: 6px;
    }
    .task-card .next-step {
      margin-top: 2px;
    }
    .entry-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .task-card .entry-actions button {
      opacity: 0.82;
    }
    .task-card .entry-actions button.primary,
    .task-card .entry-actions button:hover {
      opacity: 1;
    }
    .progress-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 4px;
      margin-bottom: 6px;
    }
    .progress-stage {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      padding: 4px 6px;
      font-size: 11px;
      text-align: center;
      opacity: 0.62;
      background: var(--vscode-sideBar-background);
    }
    .progress-stage.upcoming {
      opacity: 0.5;
      border-style: dashed;
    }
    .progress-stage.complete {
      border-color: var(--vscode-focusBorder);
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      opacity: 0.9;
    }
    .progress-stage.active {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-color: var(--vscode-button-border, transparent);
      opacity: 1;
    }
    .progress-stage.failed {
      border-color: var(--vscode-testing-iconFailed);
      color: var(--vscode-testing-iconFailed);
      opacity: 1;
    }
    .activity-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
      opacity: 0.66;
    }
    .activity-list {
      display: grid;
      gap: 3px;
      margin-bottom: 6px;
    }
    .activity-item {
      padding: 2px 0;
      font-size: 11px;
      opacity: 0.82;
    }
    .task-card.done .reply {
      font-size: 11px;
      line-height: 1.35;
      margin-bottom: 4px;
      opacity: 0.88;
    }
    .task-card.done .activity-list {
      gap: 2px;
      margin-bottom: 4px;
    }
    .task-card.done .next-step {
      font-size: 11px;
      opacity: 0.86;
    }
    .failure-card {
      border: 1px solid var(--vscode-testing-iconFailed);
      border-radius: 8px;
      padding: 6px 8px;
      margin-bottom: 8px;
      font-size: 12px;
    }
    .branch-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }
    .branch-actions button,
    .entry-actions button,
    .quick-actions button,
    #railTools button {
      padding: 6px 10px;
      font-size: 12px;
      opacity: 0.72;
    }
    .branch-actions button:hover,
    .entry-actions button:hover,
    .quick-actions button:hover,
    #railTools button:hover {
      opacity: 1;
    }
    .row {
      margin-top: 6px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    textarea {
      flex: 1;
      width: 100%;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border);
      padding: 10px;
      border-radius: 8px;
      min-height: 104px;
      font-family: var(--vscode-font-family);
      resize: vertical;
    }
    button {
      padding: 8px 12px;
      border: 1px solid var(--vscode-panel-border);
      background: var(--vscode-editor-background);
      color: var(--vscode-foreground);
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover {
      border-color: var(--vscode-focusBorder);
    }
    #recent {
      margin-top: 6px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding-top: 4px;
      border-top: 1px dashed var(--vscode-panel-border);
    }
    #railRecent {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding-top: 4px;
      border-top: 1px dashed var(--vscode-panel-border);
    }
    .chip {
      font-size: 11px;
      padding: 4px 8px;
      opacity: 0.68;
      background: var(--vscode-sideBar-background);
      border-style: dashed;
    }
    .quick-actions button {
      opacity: 0.66;
    }
    .right-rail {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 10px;
      padding: 8px;
      background: var(--vscode-editor-background);
    }
    .rail-tabs {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
      margin-bottom: 8px;
    }
    .rail-tab {
      padding: 6px 8px;
      font-size: 11px;
      border-radius: 8px;
      border: 1px solid var(--vscode-panel-border);
      background: var(--vscode-sideBar-background);
      color: var(--vscode-foreground);
      opacity: 0.8;
    }
    .rail-tab.active {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-color: var(--vscode-button-background);
      opacity: 1;
    }
    .rail-pane {
      display: none;
      font-size: 12px;
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 8px;
      background: var(--vscode-sideBar-background);
    }
    .rail-pane.active {
      display: block;
    }
    .lower-sections {
      display: grid;
      gap: 8px;
    }
    .lower-sections details {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 10px;
      padding: 6px 8px;
      background: var(--vscode-editor-background);
    }
    .secondary-diagnostics {
      font-size: 11px;
      opacity: 0.72;
      line-height: 1.4;
      border: 1px dashed var(--vscode-panel-border);
      border-radius: 8px;
      padding: 6px 8px;
      background: var(--vscode-editor-background);
      margin-bottom: 6px;
    }
    @media (max-width: 980px) {
      .layout-middle {
        grid-template-columns: minmax(0, 1fr);
      }
      .right-rail {
        order: 3;
      }
      .main-col {
        order: 2;
      }
      .rail-tabs {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 640px) {
      .top-bar {
        padding: 8px;
      }
      .status-text {
        display: none;
      }
      .progress-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .entry-actions {
        justify-content: flex-start;
      }
    }
    .diagnostic-hint {
      font-size: 12px;
      margin-bottom: 8px;
      opacity: 0.72;
    }
    .empty-state-strong {
      font-size: 12px;
      font-weight: 600;
      opacity: 0.88;
      margin-bottom: 4px;
    }
    .log-kind {
      font-weight: 600;
      margin-right: 6px;
    }
    .timestamp {
      opacity: 0.7;
      margin-right: 6px;
    }
  </style>
</head>
<body>
  <h3>aicode Chat Panel</h3>
  <div class="app-shell">
    <div class="top-bar">
      <div class="top-meta">
        <span id="runtimePill" class="status warn">Runtime: attention needed</span>
        <div class="top-status">
          <span class="status-text">Intent → Plan → Progress → Outcome</span>
          <span id="runtimeHint" class="status-hint">Recommended next step: Check Runtime, then open Runtime Details if issues persist.</span>
        </div>
      </div>
      <div class="top-actions">
        <button id="health">Check Runtime</button>
        <details class="runtime-menu">
          <summary>Runtime & Server</summary>
          <div class="row">
            <button id="startServer">Start Server</button>
            <button id="restart">Restart Server</button>
            <button id="stopServer">Stop Server</button>
            <button id="runTask">Run Task</button>
          </div>
        </details>
      </div>
    </div>

    <div class="layout-middle">
      <div class="main-col">
        <div class="panel composer-panel">
          <div class="panel-title">Request Composer</div>
          <div class="composer-subtitle">Describe the feature, bug, or refactor goal. Keep it specific to one outcome.</div>
          <div class="row">
            <textarea id="prompt" placeholder="What do you want to build or fix? Include one goal, file, or acceptance target."></textarea>
          </div>
          <div class="row">
            <button id="send" class="primary">Run Request</button>
          </div>
          <div class="row quick-actions">
            <button id="editFile">Edit File</button>
            <button id="editSelection">Edit Selection</button>
            <button id="inlineChat">Inline Chat</button>
          </div>
          <div id="recent"></div>
        </div>

        <div class="panel task-shell">
          <div class="panel-title">Current Task</div>
          <div id="currentTask" class="task-empty">No active task yet. Send a request to begin.</div>
        </div>
      </div>

      <div class="right-rail">
        <div class="panel-title">Right Rail</div>
        <div class="rail-tabs" id="railTabs">
          <button class="rail-tab active" data-tab="chat">Chat</button>
          <button class="rail-tab" data-tab="tools">Tools</button>
          <button class="rail-tab" data-tab="diagnostics">Diagnostics</button>
          <button class="rail-tab" data-tab="todos">Todos</button>
        </div>
        <div id="railChat" class="rail-pane active">
          <div class="diagnostic-hint">Recent prompts and retry chips stay here for quick replay.</div>
          <div id="railRecent"></div>
        </div>
        <div id="railTools" class="rail-pane">
          <div class="diagnostic-hint">Secondary actions for editor operations.</div>
          <div class="empty-state-strong">No extra tool action needed for most requests.</div>
          <div class="row">
            <button id="railEditFile">Edit File</button>
            <button id="railEditSelection">Edit Selection</button>
            <button id="railInlineChat">Inline Chat</button>
          </div>
        </div>
        <div id="railDiagnostics" class="rail-pane">
          <div class="diagnostic-hint">Primary diagnostics stream (detailed events) for current debugging.</div>
          <div id="actionLog"></div>
        </div>
        <div id="railTodos" class="rail-pane">
          <div class="empty-state-strong">No pending follow-up tasks for this run.</div>
          <div class="diagnostic-hint">Task follow-ups will appear here as this run model expands.</div>
        </div>
      </div>
    </div>

    <div class="lower-sections">
      <details open>
        <summary>History</summary>
        <div id="history"></div>
      </details>
      <details id="diagnosticsDetails">
        <summary>Diagnostics Summary</summary>
        <div class="secondary-diagnostics">Summary only: latest runtime/system snapshot and concise status. For full event-by-event diagnostics, use the Diagnostics tab in the right rail.</div>
        <div id="diagnosticsMirror"></div>
      </details>
      <details>
        <summary>Runtime Details</summary>
        <div id="serverStatus">Server status unknown</div>
        <div id="buildStatus">Extension build unknown</div>
      </details>
    </div>
  </div>

  <script>
    const __aicodeBoot = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : undefined;
    let __aicodeStarted = false;

    function postBootMessage(type, extra) {
      try {
        if (__aicodeBoot) {
          __aicodeBoot.postMessage({ type, ...(extra || {}) });
        }
      } catch {
      }
    }

    function reportClientError(error) {
      const message = error && error.stack ? String(error.stack) : String(error && error.message ? error.message : error);
      const status = document.getElementById('serverStatus');
      if (status) {
        status.textContent = 'Webview error: ' + message;
      }
      postBootMessage('clientError', { message });
    }

    window.addEventListener('error', (event) => {
      reportClientError(event.error || event.message || 'Unknown webview error');
    });

    window.addEventListener('unhandledrejection', (event) => {
      reportClientError(event.reason || 'Unhandled promise rejection');
    });

    const __bootStatus = document.getElementById('serverStatus');
    if (__bootStatus) {
      __bootStatus.textContent = 'Initializing panel...';
    }
    const __bootBuildStatus = document.getElementById('buildStatus');
    if (__bootBuildStatus) {
      __bootBuildStatus.textContent = 'Loading extension build metadata...';
    }

    function startPanel() {
      if (__aicodeStarted) {
        return;
      }
      __aicodeStarted = true;
      try {
        const vscode = __aicodeBoot;
        const currentTask = document.getElementById('currentTask');
        const historyList = document.getElementById('history');
        const recent = document.getElementById('recent');
        const railRecent = document.getElementById('railRecent');
        const actionLog = document.getElementById('actionLog');
        const diagnosticsMirror = document.getElementById('diagnosticsMirror');
        const diagnosticsDetails = document.getElementById('diagnosticsDetails');
        const input = document.getElementById('prompt');
        const runtimePill = document.getElementById('runtimePill');
        const runtimeHint = document.getElementById('runtimeHint');
        const send = document.getElementById('send');
        const health = document.getElementById('health');
        const startServer = document.getElementById('startServer');
        const restart = document.getElementById('restart');
        const stopServer = document.getElementById('stopServer');
        const runTask = document.getElementById('runTask');
        const editFile = document.getElementById('editFile');
        const editSelection = document.getElementById('editSelection');
        const inlineChat = document.getElementById('inlineChat');
        const railEditFile = document.getElementById('railEditFile');
        const railEditSelection = document.getElementById('railEditSelection');
        const railInlineChat = document.getElementById('railInlineChat');
        const serverStatus = document.getElementById('serverStatus');
        const buildStatus = document.getElementById('buildStatus');
        const railTabs = document.querySelectorAll('.rail-tab');
        const railPanes = {
          chat: document.getElementById('railChat'),
          tools: document.getElementById('railTools'),
          diagnostics: document.getElementById('railDiagnostics'),
          todos: document.getElementById('railTodos'),
        };

        const state = vscode.getState() || { commands: [] };
        let commandHistory = Array.isArray(state.commands) ? state.commands : [];
        const activeEntries = new Map();
        const historyIds = [];
        let currentTaskId = null;

        function switchRightRailTab(nextTab) {
          for (const tab of railTabs) {
            tab.classList.toggle('active', tab.dataset.tab === nextTab);
          }
          for (const [name, node] of Object.entries(railPanes)) {
            if (node) {
              node.classList.toggle('active', name === nextTab);
            }
          }
        }

        function shouldOfferApply(action, command, response) {
          const lowerAction = String(action || '').toLowerCase();
          const lowerCommand = String(command || '').toLowerCase();
          const lowerResponse = String(response || '').toLowerCase();
          if (['edit', 'autofix', 'self_improve_apply'].includes(lowerAction)) {
            return true;
          }
          return ['edit', 'fix', 'rewrite', 'refactor', 'apply patch', 'change'].some((token) => lowerCommand.includes(token))
            || ['patch', 'diff', 'applied changes', 'edit preview'].some((token) => lowerResponse.includes(token));
        }

        function inferNextStep(action, response, explicitNextStep) {
          const explicit = String(explicitNextStep || '').trim();
          if (explicit) {
            return explicit;
          }
          const text = String(response || '');
          const lower = text.toLowerCase();
          const marker = 'if you want, i can';
          const index = lower.indexOf(marker);
          if (index >= 0) {
            const candidate = text.slice(index).split('\\n')[0].trim();
            if (candidate) {
              return candidate;
            }
          }
          const fallback = {
            status: 'If you want, I can run full status validation next.',
            repo_summary: 'If you want, I can drill into architecture, tests, or risks next.',
            help_summary: 'If you want, I can implement one concrete improvement next.',
            research: 'If you want, I can patch one likely file from this research next.',
          };
          return fallback[String(action || '').toLowerCase()] || 'If you want, I can clarify and take the next step.';
        }

        function rememberCommand(command) {
          const next = [command, ...commandHistory.filter((item) => item !== command)];
          commandHistory = next.slice(0, 8);
          vscode.setState({ commands: commandHistory });
          renderRecent();
        }

        function createRetryChip(command) {
          const button = document.createElement('button');
          button.className = 'chip';
          button.textContent = 'Retry: ' + command;
          button.title = command;
          button.addEventListener('click', () => submit(command));
          return button;
        }

        function renderRecent() {
          if (recent) {
            recent.innerHTML = '';
          }
          if (railRecent) {
            railRecent.innerHTML = '';
          }
          for (const command of commandHistory) {
            if (recent) {
              recent.appendChild(createRetryChip(command));
            }
            if (railRecent) {
              railRecent.appendChild(createRetryChip(command));
            }
          }
        }

        function renderActionLog(entries) {
          actionLog.innerHTML = '';
          if (diagnosticsMirror) {
            diagnosticsMirror.innerHTML = '';
          }
          if (!Array.isArray(entries) || !entries.length) {
            const empty = document.createElement('div');
            empty.className = 'log-entry';
            empty.textContent = 'No actions yet.';
            actionLog.appendChild(empty);
            if (diagnosticsMirror) {
              const summary = document.createElement('div');
              summary.className = 'secondary-diagnostics';
              summary.textContent = 'No diagnostics yet. Open the Diagnostics tab in the right rail for detailed events.';
              diagnosticsMirror.appendChild(summary);
            }
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
          if (diagnosticsMirror) {
            const latest = entries[0];
            const summary = document.createElement('div');
            summary.className = 'secondary-diagnostics';
            summary.textContent =
              'Events captured: ' + String(entries.length)
              + '. Latest: [' + String(latest.kind) + '] ' + String(latest.message)
              + '. Open the Diagnostics tab for full event detail.';
            diagnosticsMirror.appendChild(summary);
          }
        }

        function formatBuildLine(build) {
          if (!build) {
            return 'Loaded extension build: unavailable';
          }
          return 'Loaded extension: v'
            + String(build.version || 'unknown')
            + ' [' + String(build.runtime_mode || 'unknown') + '] '
            + String(build.git_commit || 'unknown').slice(0, 12)
            + ' built ' + String(build.built_at || 'unknown');
        }

        function formatServerRuntime(runtime) {
          if (!runtime) {
            return '';
          }
          return 'Server runtime: v'
            + String(runtime.app_version || 'unknown')
            + ' / routing ' + String(runtime.routing_generation || 'unknown')
            + ' / commit ' + String(runtime.git_commit || 'unknown');
        }

        function formatBuildDetails(status) {
          if (!status) {
            return 'Extension build details unavailable.';
          }
          const lines = [formatBuildLine(status.extensionBuild)];
          const runtimeLine = formatServerRuntime(status.serverRuntime);
          if (runtimeLine) {
            lines.push(runtimeLine);
          }
          if (status.workspaceBuildComparison && status.workspaceBuildComparison.detail) {
            lines.push(status.workspaceBuildComparison.detail);
          }
          if (status.integrityIssue) {
            lines.push('Extension integrity: ' + status.integrityIssue);
          }
          return lines.join('\\n');
        }

        function setServerStatus(status, runtimeLabel) {
          if (!status) {
            return;
          }
          const statusText = status.detail || status.text || 'Server status unknown';
          if (serverStatus) {
            serverStatus.textContent = statusText;
          }
          if (buildStatus) {
            buildStatus.textContent = formatBuildDetails(status);
          }
          if (runtimePill) {
            runtimePill.textContent = runtimeLabel || (status.healthy ? 'Runtime: healthy' : 'Runtime: attention needed');
            runtimePill.classList.toggle('ok', Boolean(status.healthy));
            runtimePill.classList.toggle('warn', !status.healthy);
          }
          if (runtimeHint) {
            runtimeHint.textContent = status.healthy
              ? 'Recommended next step: Run Request.'
              : 'Recommended next step: Check Runtime, then review Runtime Details and Diagnostics if the issue continues.';
          }
        }

        function baseEntry(id, command) {
          return {
            id,
            command,
            action: 'pending',
            confidence: 0,
            response: '',
            status: 'Intent understood',
            nextStep: '',
            applyVisible: false,
            stage: 'intent',
            failed: false,
            failureMessage: '',
            events: [],
          };
        }

        function moveCurrentToHistory() {
          if (!currentTaskId || !activeEntries.has(currentTaskId)) {
            return;
          }
          if (!historyIds.includes(currentTaskId)) {
            historyIds.unshift(currentTaskId);
          }
        }

        function ensureEntry(id, command) {
          if (activeEntries.has(id)) {
            return activeEntries.get(id);
          }
          moveCurrentToHistory();
          const entry = baseEntry(id, command);
          activeEntries.set(id, entry);
          currentTaskId = id;
          renderCurrentTask();
          renderHistory();
          return entry;
        }

        function addTaskEvent(id, command, kind, message) {
          const entry = ensureEntry(id, command);
          const row = { kind: String(kind || 'event'), message: String(message || ''), time: new Date().toLocaleTimeString() };
          entry.events.unshift(row);
          if (entry.events.length > 12) {
            entry.events.length = 12;
          }
          renderCurrentTask();
        }

        function stageIndex(stage) {
          const map = { intent: 0, plan: 1, execute: 2, verify: 3, done: 4, failed: 3 };
          return map[stage] ?? 0;
        }

        function createProgressStrip(entry) {
          const strip = document.createElement('div');
          strip.className = 'progress-strip';
          const labels = ['Intent', 'Plan', 'Execute', 'Verify'];
          const idx = stageIndex(entry.stage);
          labels.forEach((label, i) => {
            const cell = document.createElement('div');
            cell.className = 'progress-stage';
            if (idx > i || entry.stage === 'done') {
              cell.classList.add('complete');
            } else if (idx === i) {
              cell.classList.add('active');
            } else {
              cell.classList.add('upcoming');
            }
            if (entry.failed && i === 3) {
              cell.classList.add('failed');
            }
            cell.textContent = label;
            strip.appendChild(cell);
          });
          return strip;
        }

        function createTaskCard(entry, includeBody = true) {
          const card = document.createElement('div');
          card.className = 'task-card';
          if (entry.stage === 'done') {
            card.classList.add('done');
          }

          const header = document.createElement('div');
          header.className = 'task-header';
          const titleWrap = document.createElement('div');
          const title = document.createElement('div');
          title.className = 'task-title';
          title.textContent = entry.command || 'Task';
          const status = document.createElement('div');
          status.className = 'task-status';
          status.textContent = entry.status || 'Waiting for input';
          titleWrap.appendChild(title);
          titleWrap.appendChild(status);
          const confidence = document.createElement('div');
          confidence.className = 'task-confidence';
          confidence.textContent = Math.round(Number(entry.confidence || 0) * 100) + '% confidence';
          header.appendChild(titleWrap);
          header.appendChild(confidence);
          card.appendChild(header);

          const route = document.createElement('div');
          route.className = 'task-route';
          route.textContent = 'Route: ' + String(entry.action || 'pending') + ' · Full runtime details below';
          card.appendChild(route);
          card.appendChild(createProgressStrip(entry));

          if (includeBody) {
            const reply = document.createElement('div');
            reply.className = 'reply';
            reply.textContent = entry.response || 'Working...';
            card.appendChild(reply);
          }

          if (entry.events.length) {
            const titleNode = document.createElement('div');
            titleNode.className = 'activity-title';
            titleNode.textContent = 'Task activity';
            card.appendChild(titleNode);
            const activity = document.createElement('div');
            activity.className = 'activity-list';
            for (const item of entry.events.slice(0, 5)) {
              const row = document.createElement('div');
              row.className = 'activity-item';
              row.textContent = item.message || ('[' + item.kind + ']');
              activity.appendChild(row);
            }
            card.appendChild(activity);
          }

          const nextStep = document.createElement('div');
          nextStep.className = 'next-step';
          nextStep.textContent = 'Next: ' + inferNextStep(entry.action, entry.response, entry.nextStep);
          card.appendChild(nextStep);

          if (entry.failed) {
            const failure = document.createElement('div');
            failure.className = 'failure-card';
            failure.textContent = entry.failureMessage || 'Validation failed. Choose a recovery path.';
            const branches = document.createElement('div');
            branches.className = 'branch-actions';

            const retrySame = document.createElement('button');
            retrySame.textContent = 'Retry same path';
            retrySame.addEventListener('click', () => submit(entry.command));

            const switchResearch = document.createElement('button');
            switchResearch.textContent = 'Switch to research';
            switchResearch.addEventListener('click', () => submit('research ' + entry.command));

            const clarify = document.createElement('button');
            clarify.textContent = 'Clarify request';
            clarify.addEventListener('click', () => submit('clarify this request: ' + entry.command));

            const openDiag = document.createElement('button');
            openDiag.textContent = 'Open diagnostics';
            openDiag.addEventListener('click', () => {
              switchRightRailTab('diagnostics');
              if (diagnosticsDetails) {
                diagnosticsDetails.open = true;
              }
            });

            branches.appendChild(retrySame);
            branches.appendChild(switchResearch);
            branches.appendChild(clarify);
            branches.appendChild(openDiag);
            failure.appendChild(branches);
            card.appendChild(failure);
          }

          const actions = document.createElement('div');
          actions.className = 'entry-actions';

          const retry = document.createElement('button');
          retry.textContent = 'Retry';
          retry.addEventListener('click', () => submit(entry.command));

          const clarify = document.createElement('button');
          clarify.textContent = 'Clarify';
          clarify.addEventListener('click', () => submit('clarify this request: ' + entry.command));

          const apply = document.createElement('button');
          apply.textContent = 'Apply suggested edit';
          apply.style.display = entry.applyVisible ? 'inline-block' : 'none';
          apply.addEventListener('click', () => vscode.postMessage({ type: 'editCurrentFile' }));

          actions.appendChild(retry);
          actions.appendChild(clarify);
          actions.appendChild(apply);
          card.appendChild(actions);
          return card;
        }

        function renderCurrentTask() {
          if (!currentTask) {
            return;
          }
          currentTask.innerHTML = '';
          if (!currentTaskId || !activeEntries.has(currentTaskId)) {
            currentTask.className = 'task-empty';
            currentTask.textContent = 'Current Task will appear here once you run a request. Use the composer above to start one focused outcome.';
            return;
          }
          currentTask.className = '';
          currentTask.appendChild(createTaskCard(activeEntries.get(currentTaskId), true));
        }

        function renderHistory() {
          if (!historyList) {
            return;
          }
          historyList.innerHTML = '';
          if (!historyIds.length) {
            const empty = document.createElement('div');
            empty.className = 'task-empty';
            empty.textContent = 'No completed tasks yet.';
            historyList.appendChild(empty);
            return;
          }
          for (const id of historyIds) {
            const entry = activeEntries.get(id);
            if (entry) {
              historyList.appendChild(createTaskCard(entry, false));
            }
          }
        }

        function finalizeEntry(id, command, action, confidence, response, nextStep) {
          const entry = ensureEntry(id, command);
          entry.action = String(action || 'unknown');
          entry.confidence = Number(confidence || 0);
          entry.response = String(response || '(no response)');
          entry.nextStep = String(nextStep || '');
          entry.status = 'Outcome ready';
          entry.applyVisible = shouldOfferApply(action, command, response);
          entry.stage = 'done';
          entry.failed = false;
          renderCurrentTask();
          renderHistory();
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
        startServer.addEventListener('click', () => vscode.postMessage({ type: 'startServer' }));
        restart.addEventListener('click', () => vscode.postMessage({ type: 'restartServer' }));
        stopServer.addEventListener('click', () => vscode.postMessage({ type: 'stopServer' }));
        runTask.addEventListener('click', () => vscode.postMessage({ type: 'runWorkspaceTask' }));
        editFile.addEventListener('click', () => vscode.postMessage({ type: 'editCurrentFile' }));
        editSelection.addEventListener('click', () => vscode.postMessage({ type: 'editSelection' }));
        inlineChat.addEventListener('click', () => vscode.postMessage({ type: 'inlineChat' }));
        railEditFile.addEventListener('click', () => vscode.postMessage({ type: 'editCurrentFile' }));
        railEditSelection.addEventListener('click', () => vscode.postMessage({ type: 'editSelection' }));
        railInlineChat.addEventListener('click', () => vscode.postMessage({ type: 'inlineChat' }));
        for (const tab of railTabs) {
          tab.addEventListener('click', () => switchRightRailTab(tab.dataset.tab));
        }

        input.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        });

        window.addEventListener('message', (event) => {
          const msg = event.data;
          if (msg.type === 'init') {
            renderActionLog(msg.entries || []);
            setServerStatus(msg.status, msg.runtimeLabel);
          }
          if (msg.type === 'result') {
            const requestId = msg.requestId || ('req-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7));
            finalizeEntry(requestId, msg.command || 'unknown', msg.action, msg.confidence, msg.response, msg.next_step);
          }
          if (msg.type === 'error') {
            if (msg.requestId) {
              const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
              entry.failed = true;
              entry.stage = 'failed';
              entry.status = 'Needs recovery';
              entry.failureMessage = 'Request failed: ' + String(msg.message || 'Unknown error');
              entry.response = 'ERROR: ' + String(msg.message || 'Unknown error');
              addTaskEvent(msg.requestId, msg.command || 'unknown', 'error', String(msg.message || 'Unknown error'));
              renderCurrentTask();
            } else {
              const requestId = 'err-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
              const entry = ensureEntry(requestId, msg.command || 'unknown');
              entry.failed = true;
              entry.stage = 'failed';
              entry.status = 'Needs recovery';
              entry.failureMessage = 'Request failed: ' + String(msg.message || 'Unknown error');
              entry.response = 'ERROR: ' + String(msg.message || 'Unknown error');
              renderCurrentTask();
            }
          }
          if (msg.type === 'health') {
            const requestId = 'health-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
            finalizeEntry(requestId, 'health', 'status', 1, String(msg.message || ''), 'If you want, I can run another health check next.');
          }
          if (msg.type === 'streamStart') {
            const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
            entry.stage = 'intent';
            entry.status = 'Intent understood';
            entry.response = '';
            entry.failed = false;
            addTaskEvent(msg.requestId, msg.command || 'unknown', 'intent', 'Intent captured');
          }
          if (msg.type === 'streamRoute') {
            const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
            entry.action = String(msg.action || 'unknown');
            entry.confidence = Number(msg.confidence || 0);
            entry.stage = 'plan';
            entry.status = 'Plan selected';
            addTaskEvent(msg.requestId, msg.command || 'unknown', 'route', 'Routed to ' + entry.action);
            renderCurrentTask();
          }
          if (msg.type === 'streamStatus') {
            const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
            entry.stage = 'execute';
            entry.status = String(msg.message || 'Executing');
            addTaskEvent(msg.requestId, msg.command || 'unknown', 'status', entry.status);
          }
          if (msg.type === 'streamEvent') {
            addTaskEvent(msg.requestId, msg.command || 'unknown', String(msg.kind || 'event'), String(msg.message || ''));
          }
          if (msg.type === 'streamDelta') {
            const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
            entry.stage = 'execute';
            entry.status = 'Executing';
            entry.response += String(msg.chunk || '');
            renderCurrentTask();
          }
          if (msg.type === 'streamDone') {
            const entry = ensureEntry(msg.requestId, msg.command || 'unknown');
            entry.stage = 'verify';
            addTaskEvent(msg.requestId, msg.command || 'unknown', 'verify', 'Verification completed');
            finalizeEntry(msg.requestId, msg.command || 'unknown', msg.action, msg.confidence, msg.response, msg.next_step);
          }
          if (msg.type === 'actionLog') {
            renderActionLog(msg.entries || []);
          }
          if (msg.type === 'serverStatus') {
            setServerStatus(msg.status, msg.runtimeLabel);
          }
          if (msg.type === 'prefillPrompt') {
            if (input && msg.prompt) {
              input.value = String(msg.prompt);
              input.focus();
              input.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }
        });

        postBootMessage('boot');
        renderRecent();
        renderHistory();
        setTimeout(() => vscode.postMessage({ type: 'ready' }), 0);
      } catch (error) {
        reportClientError(error);
      }
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      startPanel();
    } else {
      window.addEventListener('DOMContentLoaded', startPanel, { once: true });
      window.addEventListener('load', startPanel, { once: true });
    }
  </script>
</body>
</html>`;
}

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('aicode');
  const actionLog = new ActionLogStore(output);
  const sidebarQuickActions = new SidebarQuickActionsProvider();
  const buildInspector = new BuildRuntimeInspector(context);
  const serverManager = new ServerManager(context, output, actionLog, buildInspector);
  const commentController = vscode.comments.createCommentController('aicode-inline', 'aicode Inline');
  const inlineSuggestions = new Map<string, InlineSuggestion>();
  activeServerManager = serverManager;

  // ---------- Terminal command capture (VS Code 1.93+ shell integration) ----------
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const win = vscode.window as any;
  if (typeof win.onDidEndTerminalShellExecution === 'function') {
    context.subscriptions.push(
      win.onDidEndTerminalShellExecution((e: {
        terminal: vscode.Terminal;
        shellIntegration: { cwd?: vscode.Uri };
        execution: { commandLine: { value: string }; exitCode?: number };
      }) => {
        const cmd = e.execution?.commandLine?.value?.trim();
        if (!cmd) return;
        // Skip short/trivial commands and the aicode server itself
        if (cmd.length < 3 || cmd.startsWith('cd ') || cmd === 'ls' || cmd === 'pwd') return;
        addCapturedCommand({
          command: cmd,
          exitCode: e.execution.exitCode,
          cwd: e.shellIntegration?.cwd?.fsPath,
          timestamp: new Date().toISOString(),
        });
      }),
    );
  }
  const initialBuildSnapshot = buildInspector.snapshot();
  actionLog.append('build', formatExtensionBuildSummary(initialBuildSnapshot.extensionBuild), 'extension');
  if (initialBuildSnapshot.workspaceBuildComparison?.detail) {
    actionLog.append('build', initialBuildSnapshot.workspaceBuildComparison.detail, 'extension');
  }
  if (initialBuildSnapshot.integrityIssue) {
    actionLog.append('build', initialBuildSnapshot.integrityIssue, 'extension');
  }

  let panel: vscode.WebviewPanel | undefined;
  let panelReady = false;
  const pendingPanelMessages: unknown[] = [];
  const sidebarView = vscode.window.createTreeView('aicodeSidebarView', {
    treeDataProvider: sidebarQuickActions,
    showCollapseAll: false,
  });

  const panelDebug = (message: string): void => {
    output.appendLine(`[panel] ${message}`);
  };

  const postPanelMessage = (message: unknown): void => {
    if (!panel) {
      return;
    }
    const messageType =
      typeof message === 'object' && message !== null && 'type' in (message as Record<string, unknown>)
        ? String((message as { type?: unknown }).type ?? 'unknown')
        : 'unknown';
    if (!panelReady) {
      panelDebug(`Queue panel message: ${messageType}`);
      pendingPanelMessages.push(message);
      return;
    }
    panelDebug(`Post panel message: ${messageType}`);
    void panel.webview.postMessage(message);
  };

  const flushPanelMessages = (): void => {
    if (!panel || !panelReady || !pendingPanelMessages.length) {
      return;
    }
    panelDebug(`Flush panel messages: ${pendingPanelMessages.length}`);
    const queued = pendingPanelMessages.splice(0, pendingPanelMessages.length);
    for (const message of queued) {
      void panel.webview.postMessage(message);
    }
  };

  const syncPanelState = async (): Promise<void> => {
    panelDebug('Sync panel state');
    const entries = actionLog.getEntries();
    const cachedStatus = serverManager.getStatus();
    postPanelMessage({
      type: 'init',
      entries,
      status: cachedStatus,
      runtimeLabel: formatRuntimeStatusLabel(cachedStatus),
    });

    try {
      await serverManager.ensureModelReady();
    } catch {
      await serverManager.refreshHealth(false);
    }

    const freshStatus = serverManager.getStatus();
    postPanelMessage({
      type: 'serverStatus',
      status: freshStatus,
      runtimeLabel: formatRuntimeStatusLabel(freshStatus),
    });
  };

  const logServerEvents = (events: ActionEvent[] | undefined): void => {
    actionLog.appendMany(events, 'server');
  };

  const formatHealthSummary = (health: HealthResponse): string => {
    const runtimeMismatch = runtimeMismatchForHealth(serverManager.serverRoot(), health);
    const buildSnapshot = buildInspector.snapshot();
    const lines = [formatHealthSummaryMessage(health, normalizeBaseUrl(), runtimeMismatch)];
    lines.push(formatExtensionBuildSummary(buildSnapshot.extensionBuild));
    const serverRuntime = formatServerRuntimeSummary(health.runtime);
    if (serverRuntime) {
      lines.push(serverRuntime);
    }
    if (buildSnapshot.workspaceBuildComparison?.detail) {
      lines.push(buildSnapshot.workspaceBuildComparison.detail);
    }
    if (buildSnapshot.integrityIssue) {
      lines.push(`Extension integrity: ${buildSnapshot.integrityIssue}`);
    }
    return lines.join('\n');
  };

  const callAppCommand = async (command: string): Promise<AppCommandResponse> => {
    await serverManager.ensureModelReady();
    actionLog.append('command', command, 'client');
    return sendAppCommand(command);
  };

  const sendAppCommand = async (command: string): Promise<AppCommandResponse> => {
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
      if (shouldFallbackToNonStreaming(response.status)) {
        actionLog.append(
          'status',
          `Streaming endpoint unavailable (${response.status}); falling back to standard command mode.`,
          'extension',
        );
        const fallback = await sendAppCommand(command);
        callbacks.onRoute?.({
          action: fallback.action,
          confidence: fallback.confidence,
        });
        callbacks.onDone?.({
          action: fallback.action,
          confidence: fallback.confidence,
          response: fallback.response,
          next_step: fallback.next_step,
        });
        return fallback;
      }
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    if (!response.body) {
      actionLog.append(
        'status',
        'Streaming response body was unavailable; falling back to standard command mode.',
        'extension',
      );
      const fallback = await sendAppCommand(command);
      callbacks.onRoute?.({
        action: fallback.action,
        confidence: fallback.confidence,
      });
      callbacks.onDone?.({
        action: fallback.action,
        confidence: fallback.confidence,
        response: fallback.response,
        next_step: fallback.next_step,
      });
      return fallback;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let streamedResponse = '';
    let finalAction = 'unknown';
    let finalConfidence = 0;
    let finalNextStep = '';

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
        finalNextStep = String(payload.next_step ?? finalNextStep);
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
      next_step: finalNextStep,
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
    suggestion?: InlineSuggestion,
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
          body: buildAssistantComment(response, suggestion?.id),
          mode: vscode.CommentMode.Preview,
          author: { name: 'aicode' },
        },
      ],
    );
    thread.label = 'aicode inline chat';
    thread.collapsibleState = vscode.CommentThreadCollapsibleState.Expanded;
    thread.canReply = false;
    if (suggestion) {
      actionLog.append('suggest', `Inline suggestion ready for ${editor.document.fileName}`, 'client');
    }
    actionLog.append('chat', `Attached inline chat thread to ${editor.document.fileName}`, 'client');
  };

  actionLog.onDidChange((entries) => {
    postPanelMessage({ type: 'actionLog', entries });
  });

  serverManager.onDidChangeStatus((status) => {
    postPanelMessage({
      type: 'serverStatus',
      status,
      runtimeLabel: formatRuntimeStatusLabel(status),
    });
  });

  // ---------- Failing test message store (populated by aicode.fixFailingTests task run) ----------
  const lastFailedTestMessages: string[] = [];

  // ---------- Helper: open panel and inject a pre-filled command ----------
  const openPanelWithPrompt = async (prompt: string): Promise<void> => {
    await vscode.commands.executeCommand('aicode.openPanel');
    // Small delay to ensure panel is ready before posting
    await new Promise((r) => setTimeout(r, 150));
    postPanelMessage({ type: 'prefillPrompt', prompt });
  };

  // ===========================================================================
  // Feature: Problems panel actions
  // ===========================================================================

  const fixProblemsDisposable = vscode.commands.registerCommand(
    'aicode.fixProblems',
    async (resourceOrUri?: vscode.Uri | { resourceUri?: vscode.Uri }) => {
      // Accepts the Uri directly (problems/item/context passes the resource Uri as-is in some VS Code versions)
      let uri: vscode.Uri | undefined;
      if (resourceOrUri instanceof vscode.Uri) {
        uri = resourceOrUri;
      } else if (resourceOrUri && typeof resourceOrUri === 'object' && 'resourceUri' in resourceOrUri && resourceOrUri.resourceUri instanceof vscode.Uri) {
        uri = resourceOrUri.resourceUri;
      }
      uri = uri ?? vscode.window.activeTextEditor?.document.uri;

      if (!uri) {
        vscode.window.showWarningMessage('aicode: Open a file or select one in the Problems panel.');
        return;
      }

      const diags = vscode.languages.getDiagnostics(uri).filter(
        (d) => d.severity === vscode.DiagnosticSeverity.Error || d.severity === vscode.DiagnosticSeverity.Warning,
      );

      if (!diags.length) {
        vscode.window.showInformationMessage('aicode: No errors or warnings found in this file.');
        return;
      }

      const rel = vscode.workspace.asRelativePath(uri);
      const lines = diags.map(
        (d) => `  Line ${d.range.start.line + 1}: [${diagSeverityLabel(d.severity)}] ${d.message}${d.source ? ` (${d.source})` : ''}`,
      );
      const prompt = `Fix these ${lines.length} problem${lines.length > 1 ? 's' : ''} in ${rel}:\n${lines.join('\n')}`;
      await openPanelWithPrompt(prompt);
    },
  );

  const fixAllProblemsDisposable = vscode.commands.registerCommand('aicode.fixAllProblems', async () => {
    const all = vscode.languages.getDiagnostics();
    const errors: string[] = [];
    for (const [uri, diags] of all) {
      const relevant = diags.filter(
        (d) => d.severity === vscode.DiagnosticSeverity.Error,
      );
      if (!relevant.length) continue;
      const rel = vscode.workspace.asRelativePath(uri);
      for (const d of relevant) {
        errors.push(`${rel}:${d.range.start.line + 1}: ${d.message}`);
      }
    }
    if (!errors.length) {
      vscode.window.showInformationMessage('aicode: No errors found across the workspace.');
      return;
    }
    const summary = errors.slice(0, 40).join('\n');
    const extra = errors.length > 40 ? `\n…and ${errors.length - 40} more errors.` : '';
    await openPanelWithPrompt(`Fix these workspace errors:\n${summary}${extra}`);
  });

  // ===========================================================================
  // Feature: Search panel integration
  // ===========================================================================

  const explainSearchResultsDisposable = vscode.commands.registerCommand('aicode.explainSearchResults', async () => {
    const query = await vscode.window.showInputBox({
      prompt: 'What did you search for? (aicode will explain results and suggest next steps)',
      placeHolder: 'e.g. handleAuth OR paste a symbol/pattern you searched for',
      value: vscode.window.activeTextEditor?.document.getText(vscode.window.activeTextEditor.selection) || '',
      ignoreFocusOut: true,
    });
    if (!query) return;

    const files = await vscode.workspace.findFiles(`**/*`, '**/node_modules/**', 5);
    const fileList = files.map((f) => vscode.workspace.asRelativePath(f)).join(', ');
    const prompt = `I searched the codebase for: "${query}". Explain what this is, where it's used, and suggest what I should look at or change. Project files include: ${fileList || '(none indexed).'}`;
    await openPanelWithPrompt(prompt);
  });

  // ===========================================================================
  // Feature: Terminal command capture / replay
  // ===========================================================================

  const captureTerminalCommandDisposable = vscode.commands.registerCommand('aicode.captureTerminalCommand', async () => {
    if (!capturedTerminalCommands.length) {
      const tryIt = await vscode.window.showInformationMessage(
        'aicode: No terminal commands captured yet. Shell integration must be enabled in your terminal. Try running some commands first.',
        'Open Terminal',
      );
      if (tryIt === 'Open Terminal') {
        vscode.window.createTerminal().show();
      }
      return;
    }

    const items = capturedTerminalCommands.map((c) => ({
      label: c.command,
      description: c.exitCode !== undefined ? `exit ${c.exitCode}` : '',
      detail: `${c.cwd ? `${c.cwd}  ·  ` : ''}${new Date(c.timestamp).toLocaleTimeString()}`,
      id: c.id,
    }));

    const pick = await vscode.window.showQuickPick(items, {
      placeHolder: 'Select a captured command',
      title: 'aicode: Captured Terminal Commands',
    });
    if (!pick) return;

    const action = await vscode.window.showQuickPick(
      ['Replay in new terminal', 'Explain / fix with aicode', 'Copy to clipboard'],
      { placeHolder: 'What would you like to do?' },
    );
    if (!action) return;

    const cmd = capturedTerminalCommands.find((c) => c.id === pick.id);
    if (!cmd) return;

    if (action === 'Replay in new terminal') {
      const terminal = vscode.window.createTerminal({ name: 'aicode replay', cwd: cmd.cwd });
      terminal.show();
      terminal.sendText(cmd.command, true);
    } else if (action === 'Explain / fix with aicode') {
      const exitNote = cmd.exitCode !== undefined && cmd.exitCode !== 0
        ? ` It exited with code ${cmd.exitCode} — explain the failure and suggest a fix.`
        : ' Explain what this command does.';
      await openPanelWithPrompt(`Terminal command: \`${cmd.command}\`${exitNote}`);
    } else if (action === 'Copy to clipboard') {
      await vscode.env.clipboard.writeText(cmd.command);
      vscode.window.showInformationMessage('aicode: Command copied to clipboard.');
    }
  });

  const explainTerminalCommandDisposable = vscode.commands.registerCommand('aicode.explainTerminalCommand', async () => {
    const input = await vscode.window.showInputBox({
      prompt: 'Paste a terminal command to explain or fix',
      placeHolder: 'e.g. docker run --rm -v $(pwd):/app node:18 npm test',
      ignoreFocusOut: true,
    });
    if (!input) return;
    await openPanelWithPrompt(`Explain this terminal command and point out any issues: \`${input.trim()}\``);
  });

  // ===========================================================================
  // Feature: SCM / staging flows
  // ===========================================================================

  const reviewChangesDisposable = vscode.commands.registerCommand(
    'aicode.reviewChanges',
    async (resource?: { resourceUri?: vscode.Uri }) => {
      try {
        const git = await getGitApi();
        const repo = git?.repositories[0];
        if (!repo) {
          vscode.window.showWarningMessage('aicode: No Git repository found. Open a folder that is a git repo.');
          return;
        }

        let diff = '';
        if (resource?.resourceUri) {
          // Single file review from SCM resource context menu
          diff = await repo.diff(false);
          const rel = vscode.workspace.asRelativePath(resource.resourceUri);
          // Filter diff to just this file heuristically
          const marker = `diff --git a/${rel}`;
          const idx = diff.indexOf(marker);
          if (idx !== -1) {
            const end = diff.indexOf('\ndiff --git ', idx + 1);
            diff = end !== -1 ? diff.slice(idx, end) : diff.slice(idx);
          }
        } else {
          diff = await repo.diff(true); // staged
          if (!diff.trim()) {
            diff = await repo.diff(false); // working tree
          }
        }

        if (!diff.trim()) {
          vscode.window.showInformationMessage('aicode: No changes to review.');
          return;
        }

        const truncated = diff.length > 8000 ? diff.slice(0, 8000) + '\n…(diff truncated)' : diff;
        await openPanelWithPrompt(`Review these code changes and point out issues, risks, and improvements:\n\`\`\`diff\n${truncated}\n\`\`\``);
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`aicode: Could not get SCM diff: ${msg}`);
      }
    },
  );

  const generateCommitMessageDisposable = vscode.commands.registerCommand('aicode.generateCommitMessage', async () => {
    try {
      const git = await getGitApi();
      const repo = git?.repositories[0];
      if (!repo) {
        vscode.window.showWarningMessage('aicode: No Git repository found.');
        return;
      }

      let diff = await repo.diff(true); // staged
      if (!diff.trim()) {
        const useUnstaged = await vscode.window.showInformationMessage(
          'aicode: No staged changes found. Use unstaged (working tree) diff instead?',
          'Yes', 'No',
        );
        if (useUnstaged !== 'Yes') return;
        diff = await repo.diff(false);
      }

      if (!diff.trim()) {
        vscode.window.showInformationMessage('aicode: No changes to generate a commit message for.');
        return;
      }

      const truncated = diff.length > 6000 ? diff.slice(0, 6000) + '\n…(diff truncated)' : diff;

      const result = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'aicode: Generating commit message…' },
        () => callAppCommand(
          `Write a concise conventional-commit message (type: scope: summary) for this diff. Reply with only the commit message, no extra text:\n\`\`\`diff\n${truncated}\n\`\`\``,
        ),
      );

      const message = result.response.trim().replace(/^["']|["']$/g, '');
      if (!message) {
        vscode.window.showWarningMessage('aicode: Got an empty commit message response.');
        return;
      }

      repo.inputBox.value = message;
      logServerEvents(result.events);
      vscode.window.showInformationMessage(`aicode: Commit message set → "${message.slice(0, 72)}"`);
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      actionLog.append('error', msg, 'extension');
      vscode.window.showErrorMessage(`aicode: Could not generate commit message: ${msg}`);
    }
  });

  // ===========================================================================
  // Feature: Debugger state integration
  // ===========================================================================

  const explainDebugStateDisposable = vscode.commands.registerCommand('aicode.explainDebugState', async () => {
    const session = vscode.debug.activeDebugSession;
    if (!session) {
      const start = await vscode.window.showInformationMessage(
        'aicode: No active debug session. Start debugging first (F5), then use this command when paused at a breakpoint.',
        'Start Debugging',
      );
      if (start === 'Start Debugging') {
        await vscode.commands.executeCommand('workbench.action.debug.start');
      }
      return;
    }

    try {
      // Get threads to find the stopped one
      const threads = await session.customRequest('threads');
      const stopped = (threads?.threads ?? []).find((t: { id: number; name: string }) => t.id);
      const threadId: number = stopped?.id ?? 1;

      let frameInfo = '';
      let varsInfo = '';
      let callStackInfo = '';

      try {
        const stack = await session.customRequest('stackTrace', { threadId, levels: 5 });
        const frames: Array<{ id: number; name: string; source?: { path?: string; name?: string }; line: number }> = stack?.stackFrames ?? [];
        callStackInfo = frames
          .map((f) => `  ${f.name} @ ${f.source?.name ?? 'unknown'}:${f.line}`)
          .join('\n');
        const top = frames[0];
        if (top) {
          frameInfo = `Stopped in ${top.name} at ${top.source?.path ?? top.source?.name ?? 'unknown file'}:${top.line}`;
          try {
            const scopes = await session.customRequest('scopes', { frameId: top.id });
            const localScope = (scopes?.scopes ?? []).find((s: { name: string; variablesReference: number }) => s.name === 'Locals' || s.name === 'Local');
            if (localScope) {
              const vars = await session.customRequest('variables', { variablesReference: localScope.variablesReference });
              varsInfo = (vars?.variables ?? [])
                .slice(0, 20)
                .map((v: { name: string; value: string; type?: string }) => `  ${v.name} = ${v.value}${v.type ? ` (${v.type})` : ''}`)
                .join('\n');
            }
          } catch { /* vars not available */ }
        }
      } catch { /* stack not available */ }

      const parts = [
        `Debug session: ${session.name} (${session.type})`,
        frameInfo ? `\n${frameInfo}` : '',
        callStackInfo ? `\nCall stack:\n${callStackInfo}` : '',
        varsInfo ? `\nLocal variables:\n${varsInfo}` : '',
      ].filter(Boolean);

      const context = parts.join('\n');
      await openPanelWithPrompt(`${context}\n\nExplain what is happening at this debug breakpoint and suggest what might be wrong or what to investigate next.`);
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      vscode.window.showErrorMessage(`aicode: Could not read debug state: ${msg}`);
    }
  });

  // ===========================================================================
  // Feature: Test explorer / failing tests
  // ===========================================================================

  const fixFailingTestsDisposable = vscode.commands.registerCommand('aicode.fixFailingTests', async () => {
    if (lastFailedTestMessages.length) {
      const prompt = `Fix these failing tests:\n${lastFailedTestMessages.slice(0, 30).join('\n')}`;
      await openPanelWithPrompt(prompt);
      return;
    }

    // Fall back: run tests via workspace task and capture output
    const testTasks = (await vscode.tasks.fetchTasks()).filter(
      (t) => t.group === vscode.TaskGroup.Test || String(t.name).toLowerCase().includes('test'),
    );

    if (!testTasks.length) {
      // Ask for manual paste
      const manual = await vscode.window.showInputBox({
        prompt: 'Paste the test failure output for aicode to analyze',
        placeHolder: 'FAIL src/foo.test.ts  ● foo › should work\n  Expected: 1\n  Received: 0',
        ignoreFocusOut: true,
      });
      if (!manual) return;
      await openPanelWithPrompt(`Fix these failing tests:\n${manual}`);
      return;
    }

    const items = testTasks.map((t) => ({ label: t.name, description: t.source, task: t }));
    const pick = await vscode.window.showQuickPick(items, {
      placeHolder: 'Select a test task to run and analyze failures',
      title: 'aicode: Run & Fix Tests',
    });
    if (!pick) return;

    const output = vscode.window.createOutputChannel('aicode test run');
    const lines: string[] = [];
    const execution = await vscode.tasks.executeTask(pick.task);
    output.show(true);

    // Collect output via task end event
    await new Promise<void>((resolve) => {
      const sub = vscode.tasks.onDidEndTaskProcess((e) => {
        if (e.execution === execution) {
          sub.dispose();
          resolve();
        }
      });
      context.subscriptions.push(sub);
    });

    if (!lines.length) {
      vscode.window.showInformationMessage('aicode: Task finished. Paste any failure output for analysis.');
      return;
    }

    await openPanelWithPrompt(`Fix these failing tests:\n${lines.join('\n')}`);
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

  const startDisposable = vscode.commands.registerCommand('aicode.startServer', async () => {
    try {
      const health = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Starting aicode server…' },
        () => serverManager.start(),
      );
      const message = formatHealthSummary(health);
      actionLog.append('health', message, 'extension');
      vscode.window.showInformationMessage(message);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not start aicode server: ${message}`);
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

  const stopDisposable = vscode.commands.registerCommand('aicode.stopServer', async () => {
    try {
      await serverManager.stop();
      vscode.window.showInformationMessage('Stopped the managed aicode server/task.');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not stop aicode server: ${message}`);
    }
  });

  const startOllamaDisposable = vscode.commands.registerCommand('aicode.startOllama', async () => {
    try {
      const health = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Starting Ollama…' },
        () => serverManager.startOllama(),
      );
      const message = health.reachable
        ? `Ollama is reachable at ${defaultOllamaBaseUrl()}.`
        : `Ollama is not reachable: ${health.detail}`;
      actionLog.append('ollama', message, 'extension');
      vscode.window.showInformationMessage(message);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not start Ollama: ${message}`);
    }
  });

  const stopOllamaDisposable = vscode.commands.registerCommand('aicode.stopOllama', async () => {
    try {
      await serverManager.stopOllama();
      vscode.window.showInformationMessage('Stopped the managed Ollama task/process.');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not stop Ollama: ${message}`);
    }
  });

  const runWorkspaceTaskDisposable = vscode.commands.registerCommand('aicode.runWorkspaceTask', async () => {
    try {
      await serverManager.runWorkspaceTask();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('error', message, 'extension');
      vscode.window.showErrorMessage(`Could not run VS Code task: ${message}`);
    }
  });

  const showActionLogDisposable = vscode.commands.registerCommand('aicode.showActionLog', () => {
    output.show(true);
  });

  const applyInlineSuggestionDisposable = vscode.commands.registerCommand(
    'aicode.applyInlineSuggestion',
    async (suggestionId: string) => {
      const suggestion = inlineSuggestions.get(String(suggestionId));
      if (!suggestion) {
        vscode.window.showWarningMessage('That inline suggestion is no longer available. Re-run inline chat to regenerate it.');
        return;
      }

      try {
        const document = await vscode.workspace.openTextDocument(suggestion.uri);
        const editor = await vscode.window.showTextDocument(document, { preview: false });
        const shouldApply = await openPreviewDiff(editor, {
          path: suggestion.uri.fsPath,
          mode: suggestion.mode,
          updated_content: suggestion.updatedContent,
          diff: '',
        });
        if (!shouldApply) {
          return;
        }
        await applyUpdatedContent(editor, suggestion.updatedContent);
        inlineSuggestions.delete(suggestion.id);
        vscode.window.showInformationMessage('aicode applied the inline suggestion.');
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        actionLog.append('error', message, 'extension');
        vscode.window.showErrorMessage(`Could not apply inline suggestion: ${message}`);
      }
    },
  );

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
      const shouldPrepareSuggestion = !editor.selection.isEmpty && looksLikeEditInstruction(prompt);
      const result = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: 'Creating inline chat…' },
        async () => {
          const [chatResult, preview] = await Promise.all([
            callEditorChat(editor, prompt),
            shouldPrepareSuggestion
              ? callEditPreview(editor, prompt, true).catch((error) => {
                  const message = error instanceof Error ? error.message : String(error);
                  actionLog.append('suggest', `Inline suggestion unavailable: ${message}`, 'extension');
                  return undefined;
                })
              : Promise.resolve(undefined),
          ]);

          let suggestion: InlineSuggestion | undefined;
          if (preview) {
            const id = `inline-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
            suggestion = {
              id,
              uri: editor.document.uri,
              updatedContent: preview.updated_content,
              mode: preview.mode,
              prompt,
            };
            inlineSuggestions.set(id, suggestion);
          }
          return { chatResult, suggestion };
        },
      );
      createInlineThread(editor, prompt, result.chatResult.response, result.suggestion);
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
      void syncPanelState();
      return;
    }

    panel = vscode.window.createWebviewPanel('aicodeChatPanel', 'aicode Chat', vscode.ViewColumn.Beside, {
      enableScripts: true,
    });
    panelReady = false;
    pendingPanelMessages.length = 0;

    panel.onDidDispose(() => {
      panel = undefined;
      panelReady = false;
      pendingPanelMessages.length = 0;
    });

    panel.webview.onDidReceiveMessage(async (message: unknown) => {
      const payload =
        typeof message === 'object' && message !== null
          ? (message as { type?: string; command?: unknown })
          : {};
      panelDebug(`Panel -> extension: ${String(payload.type ?? 'unknown')}`);

      if (payload.type === 'ready' && !panelReady) {
        panelReady = true;
        flushPanelMessages();
      }

      if (payload.type === 'ready') {
        void syncPanelState();
        return;
      }

      if (payload.type === 'boot') {
        panelDebug('Panel boot message received');
        return;
      }

      if (payload.type === 'clientError') {
        const text = String((payload as { message?: unknown }).message ?? 'Unknown webview error');
        panelDebug(`Client error: ${text}`);
        actionLog.append('error', `Webview client error: ${text}`, 'extension');
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

      if (payload.type === 'startServer') {
        try {
          const health = await serverManager.start();
          postPanelMessage({
            type: 'health',
            message: formatHealthSummary(health),
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          postPanelMessage({ type: 'error', command: 'start', message: text });
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

      if (payload.type === 'stopServer') {
        try {
          await serverManager.stop();
          postPanelMessage({
            type: 'health',
            message: 'Stopped the managed aicode server/task.',
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          postPanelMessage({ type: 'error', command: 'stop', message: text });
        }
        return;
      }

      if (payload.type === 'runWorkspaceTask') {
        try {
          await serverManager.runWorkspaceTask();
          postPanelMessage({
            type: 'health',
            message: 'Started a VS Code workspace task.',
          });
        } catch (error) {
          const text = error instanceof Error ? error.message : String(error);
          postPanelMessage({ type: 'error', command: 'task', message: text });
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
          onStatus: (entry) => {
            postPanelMessage({
              type: 'streamStatus',
              requestId,
              command,
              message: String(entry.message ?? 'Working...'),
            });
          },
          onEvent: (entry) => {
            postPanelMessage({
              type: 'streamEvent',
              requestId,
              command,
              kind: String(entry.kind ?? 'event'),
              message: String(entry.message ?? ''),
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
              next_step: String(entry.next_step ?? ''),
            });
          },
        });
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        postPanelMessage({ type: 'error', requestId, command, message: text });
      }
    });

    panel.webview.html = panelHtml();

    void syncPanelState();
  });

  context.subscriptions.push(
    askDisposable,
    statusDisposable,
    startDisposable,
    restartDisposable,
    stopDisposable,
    startOllamaDisposable,
    stopOllamaDisposable,
    runWorkspaceTaskDisposable,
    showActionLogDisposable,
    applyInlineSuggestionDisposable,
    editCurrentFileDisposable,
    editSelectionDisposable,
    inlineChatDisposable,
    panelDisposable,
    // Problems panel
    fixProblemsDisposable,
    fixAllProblemsDisposable,
    // Search
    explainSearchResultsDisposable,
    // Terminal
    captureTerminalCommandDisposable,
    explainTerminalCommandDisposable,
    // SCM
    reviewChangesDisposable,
    generateCommitMessageDisposable,
    // Debug / Tests
    explainDebugStateDisposable,
    fixFailingTestsDisposable,
    sidebarView,
    output,
    actionLog,
    serverManager,
    commentController,
    vscode.window.onDidCloseTerminal((terminal) => {
      serverManager.handleTerminalClosed(terminal);
    }),
    vscode.workspace.onDidChangeWorkspaceFolders((event) => {
      if (!shouldStopManagedServerOnDeactivate()) {
        return;
      }
      const noWorkspaceOpen = (vscode.workspace.workspaceFolders ?? []).length === 0;
      if (!noWorkspaceOpen) {
        return;
      }
      void serverManager.shutdownManagedServer('All workspace folders closed');
    }),
  );

  if (serverManager.autoStartEnabled()) {
    void serverManager.ensureModelReady().catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      actionLog.append('health', `Auto-start failed: ${message}`, 'extension');
    });
  }
}

let activeServerManager: ServerManager | undefined;

export async function deactivate(): Promise<void> {
  const manager = activeServerManager;
  activeServerManager = undefined;
  if (!manager) {
    return;
  }
  try {
    if (shouldStopManagedServerOnDeactivate()) {
      await manager.shutdownManagedServer('Extension deactivated');
    }
  } finally {
    manager.dispose();
  }
}
