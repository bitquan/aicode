const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  compareWorkspaceBuilds,
  buildOllamaGuidance,
  detectExtensionRuntimeMode,
  describeRuntimeMismatch,
  discoverServerRoot,
  discoverWorkspaceExtensionRoot,
  formatExtensionBuildSummary,
  formatHealthSummaryMessage,
  formatRuntimeStatusLabel,
  hashFileSha256,
  loadExtensionBuildInfo,
  loadRuntimeManifest,
  looksLikeEditInstruction,
  normalizeOllamaHealth,
  shouldFallbackToNonStreaming,
  validateExtensionBuildInfo,
} = require('../out/runtime_support.js');

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'aicode-ext-smoke-'));
}

test('discoverServerRoot finds coding-ai-app inside the open parent workspace', () => {
  const tempDir = makeTempDir();
  const workspaceRoot = path.join(tempDir, 'aicode');
  const repoRoot = path.join(workspaceRoot, 'coding-ai-app');
  const extensionInstall = path.join(tempDir, '.vscode', 'extensions', 'aicode-local.aicode-thin-client-0.1.4');

  fs.mkdirSync(path.join(repoRoot, 'src'), { recursive: true });
  fs.writeFileSync(path.join(repoRoot, 'src', 'server.py'), '# smoke\n', 'utf8');
  fs.mkdirSync(extensionInstall, { recursive: true });

  assert.equal(discoverServerRoot([workspaceRoot], extensionInstall), repoRoot);
});

test('discoverWorkspaceExtensionRoot finds the repo extension inside the parent workspace', () => {
  const tempDir = makeTempDir();
  const workspaceRoot = path.join(tempDir, 'aicode');
  const extensionRoot = path.join(workspaceRoot, 'coding-ai-app', 'vscode-extension');

  fs.mkdirSync(path.join(extensionRoot, 'src'), { recursive: true });
  fs.writeFileSync(path.join(extensionRoot, 'src', 'extension.ts'), '// smoke\n', 'utf8');
  fs.writeFileSync(path.join(extensionRoot, 'package.json'), '{"name":"aicode-thin-client"}\n', 'utf8');

  assert.equal(discoverWorkspaceExtensionRoot([workspaceRoot]), extensionRoot);
});

test('normalizeOllamaHealth tolerates missing payload fields', () => {
  assert.deepEqual(normalizeOllamaHealth({}, 'http://127.0.0.1:11434'), {
    reachable: false,
    detail: 'unknown. Start Ollama with "ollama serve" and retry. Expected Ollama URL: http://127.0.0.1:11434.',
    model_available: false,
  });
});

test('looksLikeEditInstruction only flags actual edit-style prompts', () => {
  assert.equal(looksLikeEditInstruction('Please refactor this loop to be safer'), true);
  assert.equal(looksLikeEditInstruction('Explain what this function does'), false);
});

test('buildOllamaGuidance gives actionable startup text', () => {
  const guidance = buildOllamaGuidance('http://127.0.0.1:11434');
  assert.match(guidance, /ollama serve/);
  assert.match(guidance, /127\.0\.0\.1:11434/);
});

test('shouldFallbackToNonStreaming only falls back for missing stream support', () => {
  assert.equal(shouldFallbackToNonStreaming(404), true);
  assert.equal(shouldFallbackToNonStreaming(405), true);
  assert.equal(shouldFallbackToNonStreaming(500), false);
});

test('loadRuntimeManifest reads the shared backend runtime manifest', () => {
  const tempDir = makeTempDir();
  const serverRoot = path.join(tempDir, 'coding-ai-app');
  fs.mkdirSync(path.join(serverRoot, 'src', 'config'), { recursive: true });
  fs.writeFileSync(
    path.join(serverRoot, 'src', 'config', 'runtime_manifest.json'),
    JSON.stringify({ manifest_version: 1, app_version: '0.1.0', routing_generation: 3, readiness_suite_version: 1 }),
    'utf8',
  );

  assert.deepEqual(loadRuntimeManifest(serverRoot), {
    manifest_version: 1,
    app_version: '0.1.0',
    routing_generation: 3,
    readiness_suite_version: 1,
  });
});

test('extension build metadata loads and validates against the compiled bundle', () => {
  const tempDir = makeTempDir();
  const extensionRoot = path.join(tempDir, 'vscode-extension');
  const bundlePath = path.join(extensionRoot, 'out', 'extension.js');
  const bundleContent = 'console.log("aicode");\n';

  fs.mkdirSync(path.join(extensionRoot, 'out'), { recursive: true });
  fs.writeFileSync(bundlePath, bundleContent, 'utf8');
  fs.writeFileSync(
    path.join(extensionRoot, 'build_manifest.json'),
    JSON.stringify({
      version: '0.1.5',
      git_commit: 'abc123def456',
      built_at: '2026-04-02T00:00:00Z',
      bundle_hash: hashFileSha256(bundlePath),
      runtime_mode: 'installed',
    }),
    'utf8',
  );

  const info = loadExtensionBuildInfo(extensionRoot, 'installed');
  assert.equal(info.version, '0.1.5');
  assert.equal(info.runtime_mode, 'installed');
  assert.equal(validateExtensionBuildInfo(extensionRoot, info), undefined);
  assert.match(formatExtensionBuildSummary(info), /Loaded extension: v0\.1\.5/);
});

test('compareWorkspaceBuilds flags a stale install when workspace build differs', () => {
  const comparison = compareWorkspaceBuilds(
    {
      version: '0.1.4',
      git_commit: 'loaded1234567',
      built_at: '2026-04-02T00:00:00Z',
      bundle_hash: 'aaa',
      runtime_mode: 'installed',
    },
    {
      version: '0.1.5',
      git_commit: 'workspace7654321',
      built_at: '2026-04-02T01:00:00Z',
      bundle_hash: 'bbb',
      runtime_mode: 'workspace',
    },
  );

  assert.equal(comparison.state, 'stale-install');
  assert.match(comparison.detail, /Install the latest verified VSIX/);
  assert.equal(
    formatRuntimeStatusLabel({ healthy: true, workspaceBuildComparison: comparison }),
    'Runtime: stale install',
  );
});

test('detectExtensionRuntimeMode distinguishes dev host from installed builds', () => {
  const workspaceRoot = '/tmp/coding-ai-app/vscode-extension';
  assert.equal(
    detectExtensionRuntimeMode(workspaceRoot, workspaceRoot),
    'development-host',
  );
  assert.equal(
    detectExtensionRuntimeMode('/Users/example/.vscode/extensions/aicode-local', workspaceRoot),
    'installed',
  );
});

test('describeRuntimeMismatch flags stale backend generations', () => {
  const message = describeRuntimeMismatch(
    { manifest_version: 1, app_version: '0.1.0', routing_generation: 3, readiness_suite_version: 1 },
    { routing_generation: 2, app_version: '0.1.0' },
  );
  assert.match(message, /Stale server detected/);
});

test('formatHealthSummaryMessage returns conversational runtime summary', () => {
  const summary = formatHealthSummaryMessage(
    {
      model: 'qwen2.5-coder:7b',
      base_url: 'http://127.0.0.1:11434',
      ollama: { reachable: true, detail: 'ok', model_available: true },
      runtime: { app_version: '0.1.0', routing_generation: 4 },
    },
    'http://127.0.0.1:8005',
  );

  assert.match(summary, /Server is up at http:\/\/127\.0\.0\.1:8005/);
  assert.match(summary, /Ollama is reachable at http:\/\/127\.0\.0\.1:11434/);
  assert.match(summary, /Runtime: v0\.1\.0 \/ routing 4/);
});
