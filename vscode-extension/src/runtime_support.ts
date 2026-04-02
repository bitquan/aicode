import * as fs from 'fs';
import * as path from 'path';

export const DEFAULT_OLLAMA_BASE_URL = 'http://127.0.0.1:11434';

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
  runtime?: Partial<RuntimeMetadata>;
};

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
