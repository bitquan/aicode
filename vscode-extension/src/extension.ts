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
      padding: 12px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    h3 { margin-bottom: 10px; }
    .meta {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
      opacity: 0.9;
      font-size: 12px;
      flex-wrap: wrap;
    }
    .status {
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--vscode-panel-border);
    }
    .status.ok {
      border-color: var(--vscode-testing-iconPassed);
      color: var(--vscode-testing-iconPassed);
    }
    .status.warn {
      border-color: var(--vscode-testing-iconFailed);
      color: var(--vscode-testing-iconFailed);
    }
    .panel {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 10px;
    }
    .panel-title {
      font-weight: 600;
      margin-bottom: 8px;
    }
    .runtime-details {
      margin-bottom: 10px;
    }
    .runtime-details > summary,
    details > summary {
      cursor: pointer;
      font-weight: 600;
    }
    #serverStatus {
      margin-top: 8px;
      margin-bottom: 6px;
      white-space: pre-wrap;
      font-size: 12px;
      opacity: 0.9;
    }
    #buildStatus {
      margin-bottom: 8px;
      white-space: pre-wrap;
      font-size: 12px;
      opacity: 0.9;
    }
    .task-shell {
      min-height: 140px;
    }
    .task-empty {
      border: 1px dashed var(--vscode-panel-border);
      border-radius: 8px;
      padding: 12px;
      opacity: 0.8;
      font-size: 12px;
    }
    #history {
      max-height: 40vh;
      overflow: auto;
    }
    #actionLog {
      max-height: 160px;
      overflow: auto;
      font-size: 12px;
    }
    .entry, .log-entry {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      padding: 8px;
      margin-bottom: 8px;
      background: var(--vscode-editor-background);
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
  </style>
</head>
<body>
  <h3>aicode Chat Panel</h3>
  <div class="meta">
    <span id="runtimePill" class="status warn">Runtime: attention needed</span>
    <span>Task-first view: compose, track current task, then review history.</span>
  </div>
  <details class="runtime-details">
    <summary>Runtime details</summary>
    <div id="serverStatus">Server status unknown</div>
    <div id="buildStatus">Extension build unknown</div>
    <div class="row">
      <button id="health">Check API</button>
      <button id="startServer">Start Server</button>
      <button id="restart">Restart Server</button>
      <button id="stopServer">Stop Server</button>
      <button id="runTask">Run Task</button>
    </div>
  </details>

  <div class="panel">
    <div class="panel-title">Composer</div>
    <div class="row">
      <input id="prompt" placeholder="Ask for status, repo summary, or a code change" />
      <button id="send">Send</button>
    </div>
    <div class="row">
      <button id="editFile">Edit File</button>
      <button id="editSelection">Edit Selection</button>
      <button id="inlineChat">Inline Chat</button>
    </div>
    <div id="recent"></div>
  </div>

  <div class="panel task-shell">
    <div class="panel-title">Current Task</div>
    <div id="currentTask" class="task-empty">No active task yet. Send a command to start one.</div>
    <details>
      <summary>Diagnostics</summary>
      <div id="actionLog"></div>
    </details>
  </div>

  <details class="panel" open>
    <summary>History</summary>
    <div id="history"></div>
  </details>

  <script>
    const __aicodeBoot = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : undefined;
    let __aicodeStarted = false;

    function postBootMessage(type, extra) {
      try {
        if (__aicodeBoot) {
          __aicodeBoot.postMessage({ type, ...(extra || {}) });
        }
      } catch {
        // Ignore bootstrap reporting failures.
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
    // Reuse the already-acquired API instance — acquireVsCodeApi() can only be called once.
    const vscode = __aicodeBoot;
    const currentTask = document.getElementById('currentTask');
    const historyList = document.getElementById('history');
    const recent = document.getElementById('recent');
    const actionLog = document.getElementById('actionLog');
    const input = document.getElementById('prompt');
    const runtimePill = document.getElementById('runtimePill');
    const send = document.getElementById('send');
    const health = document.getElementById('health');
    const startServer = document.getElementById('startServer');
    const restart = document.getElementById('restart');
    const stopServer = document.getElementById('stopServer');
    const runTask = document.getElementById('runTask');
    const editFile = document.getElementById('editFile');
    const editSelection = document.getElementById('editSelection');
    const inlineChat = document.getElementById('inlineChat');
    const serverStatus = document.getElementById('serverStatus');
    const buildStatus = document.getElementById('buildStatus');
    const state = vscode.getState() || { commands: [] };
    let commandHistory = Array.isArray(state.commands) ? state.commands : [];
    const activeEntries = new Map();
    let currentTaskId = null;

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
        const candidate = text.slice(index).split('\n')[0].trim();
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
    }

    function moveCurrentToHistory() {
      if (!currentTaskId || !activeEntries.has(currentTaskId)) {
        return;
      }
      const previous = activeEntries.get(currentTaskId);
      if (previous && previous.card && historyList) {
        historyList.prepend(previous.card);
      }
    }

    function ensureEntry(id, command) {
      if (activeEntries.has(id)) {
        return activeEntries.get(id);
      }

      moveCurrentToHistory();

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

      const clarify = document.createElement('button');
      clarify.textContent = 'Clarify';
      clarify.addEventListener('click', () => submit('clarify this request: ' + command));
      actions.appendChild(clarify);

      const apply = document.createElement('button');
      apply.textContent = 'Apply suggested edit';
      apply.style.display = 'none';
      apply.addEventListener('click', () => vscode.postMessage({ type: 'editCurrentFile' }));
      actions.appendChild(apply);

      card.appendChild(prompt);
      card.appendChild(meta);
      card.appendChild(reply);
      card.appendChild(actions);

      currentTask.innerHTML = '';
      currentTask.className = '';
      currentTask.appendChild(card);

      const entry = { card, meta, reply, apply };
      activeEntries.set(id, entry);
      currentTaskId = id;
      return entry;
    }

    function finalizeEntry(id, command, action, confidence, response, nextStep) {
      const entry = ensureEntry(id, command);
      entry.meta.textContent = '[action=' + String(action || 'unknown') + ', confidence=' + Number(confidence || 0) + ']';
      const suggestion = inferNextStep(action, response, nextStep);
      entry.reply.textContent = String(response || '(no response)') + '\n\nNext: ' + suggestion;
      entry.apply.style.display = shouldOfferApply(action, command, response) ? 'inline-block' : 'none';
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
      if (historyList) {
        historyList.scrollTop = historyList.scrollHeight;
      }
    }

    function appendToEntry(id, command, chunk) {
      const entry = ensureEntry(id, command);
      entry.reply.textContent += chunk;
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
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
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
        finalizeEntry(
          requestId,
          msg.command || 'unknown',
          msg.action,
          msg.confidence,
          msg.response,
          msg.next_step,
        );
      }
      if (msg.type === 'error') {
        if (msg.requestId) {
          finalizeEntry(
            msg.requestId,
            msg.command || 'unknown',
            'error',
            0,
            'ERROR: ' + msg.message,
            'If you want, I can retry or clarify this request next.',
          );
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
        finalizeEntry(
          msg.requestId,
          msg.command || 'unknown',
          msg.action,
          msg.confidence,
          msg.response,
          msg.next_step,
        );
      }
      if (msg.type === 'actionLog') {
        renderActionLog(msg.entries || []);
      }
      if (msg.type === 'serverStatus') {
        setServerStatus(msg.status, msg.runtimeLabel);
      }
    });

    postBootMessage('boot');
    renderRecent();
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
