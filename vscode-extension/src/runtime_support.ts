import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

export const DEFAULT_OLLAMA_BASE_URL = 'http://127.0.0.1:11434';
export const EXTENSION_BUILD_MANIFEST = 'build_manifest.json';

export type OllamaHealth = {
  reachable: boolean;
  detail: string;
  model_available: boolean;
};

export type RuntimeManifest = {
  manifest_version: number;
  app_version: string;
  routing_generation: number;
  readiness_suite_version: number;
};

export type RuntimeMetadata = RuntimeManifest & {
  started_at?: string;
  pid?: number;
  git_commit?: string;
  workspace_root?: string;
};

export type HealthLike = {
  ollama?: Partial<OllamaHealth>;
  base_url?: string;
  model?: string;
  runtime?: Partial<RuntimeMetadata>;
};

export type RuntimeStatusLike = {
  healthy?: boolean;
  integrityIssue?: string;
  workspaceBuildComparison?: WorkspaceBuildComparison;
};

export function formatRuntimeStatusLabel(status: RuntimeStatusLike | undefined): string {
  if (status?.integrityIssue) {
    return 'Runtime: build integrity issue';
  }
  if (status?.workspaceBuildComparison?.state === 'stale-install') {
    return 'Runtime: stale install';
  }
  return status?.healthy ? 'Runtime: healthy' : 'Runtime: attention needed';
}

export type ExtensionRuntimeMode = 'installed' | 'development-host' | 'workspace';

export type ExtensionBuildManifest = {
  version: string;
  git_commit: string;
  built_at: string;
  bundle_hash: string;
  runtime_mode?: string;
};

export type ExtensionBuildInfo = {
  version: string;
  git_commit: string;
  built_at: string;
  bundle_hash: string;
  runtime_mode: ExtensionRuntimeMode;
};

export type WorkspaceBuildComparisonState =
  | 'match'
  | 'stale-install'
  | 'workspace-build-missing'
  | 'development-host';

export type WorkspaceBuildComparison = {
  state: WorkspaceBuildComparisonState;
  detail: string;
  workspace_build?: ExtensionBuildInfo;
};

export type ExtensionBuildSnapshot = {
  extensionBuild?: ExtensionBuildInfo;
  workspaceBuildComparison?: WorkspaceBuildComparison;
  integrityIssue?: string;
};

export function formatHealthSummaryMessage(
  health: HealthLike | undefined,
  serverUrl: string,
  runtimeMismatch?: string,
): string {
  const model = typeof health?.model === 'string' && health.model ? health.model : 'unknown-model';
  const ollamaBase = typeof health?.base_url === 'string' && health.base_url ? health.base_url : DEFAULT_OLLAMA_BASE_URL;
  const ollama = normalizeOllamaHealth(health, ollamaBase);
  const ollamaSummary = ollama.reachable
    ? `Ollama is reachable at ${ollamaBase}.`
    : `Ollama is unavailable at ${ollamaBase}: ${ollama.detail} ${buildOllamaGuidance(ollamaBase)}`;
  const runtimeSummary =
    health?.runtime && typeof health.runtime === 'object'
      ? ` Runtime: v${String(health.runtime.app_version ?? 'unknown')} / routing ${String(health.runtime.routing_generation ?? 'unknown')}.`
      : '';
  const mismatchSummary = runtimeMismatch ? ` ${runtimeMismatch}` : '';

  return `Server is up at ${serverUrl} using ${model}. ${ollamaSummary}${runtimeSummary}${mismatchSummary}`;
}

export function buildOllamaGuidance(baseUrl: string): string {
  return `Start Ollama with "ollama serve" and retry. Expected Ollama URL: ${baseUrl}.`;
}

export function normalizeOllamaHealth(
  health: HealthLike | undefined,
  fallbackBaseUrl = DEFAULT_OLLAMA_BASE_URL,
): OllamaHealth {
  const candidate = health?.ollama;
  return {
    reachable: Boolean(candidate?.reachable),
    detail:
      typeof candidate?.detail === 'string'
        ? candidate.detail
        : `unknown. ${buildOllamaGuidance(fallbackBaseUrl)}`,
    model_available: Boolean(candidate?.model_available),
  };
}

export function isValidServerRoot(
  candidate: string,
  existsSync: (filePath: string) => boolean = fs.existsSync,
): boolean {
  return existsSync(path.join(candidate, 'src', 'server.py'));
}

export function discoverServerRoot(
  workspaceFolders: string[],
  extensionPath: string,
  existsSync: (filePath: string) => boolean = fs.existsSync,
  readdirSync: typeof fs.readdirSync = fs.readdirSync,
): string | undefined {
  const candidates = new Set<string>();

  for (const folder of workspaceFolders) {
    candidates.add(folder);
    candidates.add(path.join(folder, 'coding-ai-app'));

    try {
      const children = readdirSync(folder, { withFileTypes: true });
      for (const child of children) {
        if (!child.isDirectory()) {
          continue;
        }
        const childPath = path.join(folder, child.name);
        candidates.add(childPath);
        candidates.add(path.join(childPath, 'coding-ai-app'));
      }
    } catch {
      // Ignore unreadable folders; callers can fall back to diagnostics.
    }
  }

  const devRoot = path.resolve(extensionPath, '..');
  candidates.add(devRoot);

  for (const candidate of candidates) {
    if (isValidServerRoot(candidate, existsSync)) {
      return candidate;
    }
  }

  return undefined;
}

export function looksLikeEditInstruction(prompt: string): boolean {
  const lower = prompt.toLowerCase();
  return [
    'fix',
    'change',
    'refactor',
    'rewrite',
    'rename',
    'update',
    'improve',
    'simplify',
    'optimize',
    'clean up',
    'convert',
    'replace',
    'make this',
    'apply',
    'edit',
    'remove',
    'add ',
  ].some((signal) => lower.includes(signal));
}

export function shouldFallbackToNonStreaming(status: number): boolean {
  return status === 404 || status === 405;
}

export function loadRuntimeManifest(
  serverRoot: string,
  existsSync: (filePath: string) => boolean = fs.existsSync,
  readFileSync: typeof fs.readFileSync = fs.readFileSync,
): RuntimeManifest | undefined {
  const manifestPath = path.join(serverRoot, 'src', 'config', 'runtime_manifest.json');
  if (!existsSync(manifestPath)) {
    return undefined;
  }
  try {
    return JSON.parse(readFileSync(manifestPath, 'utf8')) as RuntimeManifest;
  } catch {
    return undefined;
  }
}

export function describeRuntimeMismatch(
  expected: RuntimeManifest | undefined,
  actual: Partial<RuntimeMetadata> | undefined,
): string | undefined {
  if (!expected || !actual) {
    return undefined;
  }
  const actualGeneration = Number(actual.routing_generation ?? 0);
  const expectedGeneration = Number(expected.routing_generation ?? 0);
  if (actualGeneration >= expectedGeneration) {
    return undefined;
  }
  return (
    `Stale server detected: running routing generation ${actualGeneration}, ` +
    `workspace expects ${expectedGeneration}. Restart the local server.`
  );
}

export function isValidExtensionRoot(
  candidate: string,
  existsSync: (filePath: string) => boolean = fs.existsSync,
): boolean {
  return (
    existsSync(path.join(candidate, 'package.json'))
    && existsSync(path.join(candidate, 'src', 'extension.ts'))
  );
}

export function discoverWorkspaceExtensionRoot(
  workspaceFolders: string[],
  existsSync: (filePath: string) => boolean = fs.existsSync,
  readdirSync: typeof fs.readdirSync = fs.readdirSync,
): string | undefined {
  const candidates = new Set<string>();

  for (const folder of workspaceFolders) {
    candidates.add(path.join(folder, 'vscode-extension'));
    candidates.add(path.join(folder, 'coding-ai-app', 'vscode-extension'));

    try {
      const children = readdirSync(folder, { withFileTypes: true });
      for (const child of children) {
        if (!child.isDirectory()) {
          continue;
        }
        candidates.add(path.join(folder, child.name, 'vscode-extension'));
      }
    } catch {
      // Ignore unreadable folders; callers can fall back to diagnostics.
    }
  }

  for (const candidate of candidates) {
    if (isValidExtensionRoot(candidate, existsSync)) {
      return candidate;
    }
  }

  return undefined;
}

export function detectExtensionRuntimeMode(
  extensionPath: string,
  workspaceExtensionRoot: string | undefined,
): ExtensionRuntimeMode {
  if (
    workspaceExtensionRoot
    && path.resolve(extensionPath) === path.resolve(workspaceExtensionRoot)
  ) {
    return 'development-host';
  }
  return 'installed';
}

function normalizeExtensionBuildManifest(
  payload: unknown,
  runtimeMode: ExtensionRuntimeMode,
): ExtensionBuildInfo | undefined {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }
  const record = payload as Partial<ExtensionBuildManifest>;
  if (
    typeof record.version !== 'string'
    || typeof record.git_commit !== 'string'
    || typeof record.built_at !== 'string'
    || typeof record.bundle_hash !== 'string'
  ) {
    return undefined;
  }
  return {
    version: record.version,
    git_commit: record.git_commit,
    built_at: record.built_at,
    bundle_hash: record.bundle_hash,
    runtime_mode: runtimeMode,
  };
}

export function hashFileSha256(
  filePath: string,
  readFileSync: typeof fs.readFileSync = fs.readFileSync,
): string | undefined {
  try {
    return createHash('sha256').update(readFileSync(filePath)).digest('hex');
  } catch {
    return undefined;
  }
}

export function loadExtensionBuildInfo(
  extensionRoot: string,
  runtimeMode: ExtensionRuntimeMode,
  existsSync: (filePath: string) => boolean = fs.existsSync,
  readFileSync: typeof fs.readFileSync = fs.readFileSync,
): ExtensionBuildInfo | undefined {
  const manifestPath = path.join(extensionRoot, EXTENSION_BUILD_MANIFEST);
  if (!existsSync(manifestPath)) {
    return undefined;
  }
  try {
    return normalizeExtensionBuildManifest(
      JSON.parse(readFileSync(manifestPath, 'utf8')),
      runtimeMode,
    );
  } catch {
    return undefined;
  }
}

export function validateExtensionBuildInfo(
  extensionRoot: string,
  info: ExtensionBuildInfo | undefined,
  existsSync: (filePath: string) => boolean = fs.existsSync,
  readFileSync: typeof fs.readFileSync = fs.readFileSync,
): string | undefined {
  if (!info) {
    return 'Loaded extension build metadata is missing. Rebuild or reinstall from a verified VSIX.';
  }

  const bundlePath = path.join(extensionRoot, 'out', 'extension.js');
  if (!existsSync(bundlePath)) {
    return 'Loaded extension bundle is missing out/extension.js.';
  }

  const actualHash = hashFileSha256(bundlePath, readFileSync);
  if (!actualHash) {
    return 'Loaded extension bundle hash could not be calculated.';
  }
  if (actualHash !== info.bundle_hash) {
    return (
      `Loaded extension bundle hash mismatch: manifest ${info.bundle_hash.slice(0, 12)}, ` +
      `actual ${actualHash.slice(0, 12)}.`
    );
  }
  return undefined;
}

export function compareWorkspaceBuilds(
  loaded: ExtensionBuildInfo | undefined,
  workspace: ExtensionBuildInfo | undefined,
): WorkspaceBuildComparison | undefined {
  if (!workspace) {
    return undefined;
  }
  if (loaded?.runtime_mode === 'development-host') {
    return {
      state: 'development-host',
      detail: 'Running the workspace build directly in Extension Development Host.',
      workspace_build: workspace,
    };
  }
  if (
    loaded
    && loaded.version === workspace.version
    && loaded.git_commit === workspace.git_commit
    && loaded.bundle_hash === workspace.bundle_hash
  ) {
    return {
      state: 'match',
      detail: `Installed extension matches the workspace build (v${workspace.version}, ${workspace.git_commit.slice(0, 12)}).`,
      workspace_build: workspace,
    };
  }
  const loadedLabel = loaded
    ? `loaded v${loaded.version} (${loaded.git_commit.slice(0, 12)})`
    : 'loaded build metadata unavailable';
  return {
    state: 'stale-install',
    detail: (
      `Stale install detected: ${loadedLabel}, workspace build v${workspace.version} ` +
      `(${workspace.git_commit.slice(0, 12)}). Install the latest verified VSIX.`
    ),
    workspace_build: workspace,
  };
}

export function describeWorkspaceBuildMissing(): WorkspaceBuildComparison {
  return {
    state: 'workspace-build-missing',
    detail: 'Workspace extension source is open, but build metadata is missing. Run npm run compile:clean to compare it against the loaded extension.',
  };
}

export function formatExtensionBuildSummary(info: ExtensionBuildInfo | undefined): string {
  if (!info) {
    return 'Loaded extension build: unavailable';
  }
  return (
    `Loaded extension: v${info.version} ` +
    `[${info.runtime_mode}] ` +
    `${info.git_commit.slice(0, 12)} ` +
    `built ${info.built_at}`
  );
}

export function formatServerRuntimeSummary(runtime: Partial<RuntimeMetadata> | undefined): string | undefined {
  if (!runtime) {
    return undefined;
  }
  return (
    `Server runtime: v${String(runtime.app_version ?? 'unknown')} ` +
    `/ routing ${String(runtime.routing_generation ?? 'unknown')} ` +
    `/ commit ${String(runtime.git_commit ?? 'unknown')}`
  );
}
