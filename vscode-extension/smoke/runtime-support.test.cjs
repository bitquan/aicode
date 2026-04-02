const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  buildOllamaGuidance,
  describeRuntimeMismatch,
  discoverServerRoot,
  loadRuntimeManifest,
  looksLikeEditInstruction,
  normalizeOllamaHealth,
  shouldFallbackToNonStreaming,
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

test('describeRuntimeMismatch flags stale backend generations', () => {
  const message = describeRuntimeMismatch(
    { manifest_version: 1, app_version: '0.1.0', routing_generation: 3, readiness_suite_version: 1 },
    { routing_generation: 2, app_version: '0.1.0' },
  );
  assert.match(message, /Stale server detected/);
});
