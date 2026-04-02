const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  buildVsixFilename,
  bumpPatchVersion,
  sha256Buffer,
  verifyVsixFile,
} = require('../scripts/build_utils.js');

function makeTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'aicode-vsix-smoke-'));
}

function createVsixFixture(version, manifestOverrides = {}) {
  const tempDir = makeTempDir();
  const extensionDir = path.join(tempDir, 'extension');
  const outDir = path.join(extensionDir, 'out');
  const mediaDir = path.join(extensionDir, 'media');
  const extensionBundle = Buffer.from('console.log("extension build");\n', 'utf8');

  fs.mkdirSync(outDir, { recursive: true });
  fs.mkdirSync(mediaDir, { recursive: true });
  fs.writeFileSync(path.join(extensionDir, 'package.json'), JSON.stringify({ name: 'aicode-thin-client', version }), 'utf8');
  fs.writeFileSync(path.join(outDir, 'extension.js'), extensionBundle);
  fs.writeFileSync(path.join(outDir, 'runtime_support.js'), 'module.exports = {};\n', 'utf8');
  fs.writeFileSync(path.join(extensionDir, 'LICENSE.txt'), 'MIT\n', 'utf8');
  fs.writeFileSync(path.join(extensionDir, 'readme.md'), '# aicode\n', 'utf8');
  fs.writeFileSync(path.join(mediaDir, 'aicode.svg'), '<svg></svg>\n', 'utf8');

  const manifest = {
    version,
    git_commit: 'abc123def456',
    built_at: '2026-04-02T00:00:00Z',
    bundle_hash: sha256Buffer(extensionBundle),
    runtime_mode: 'installed',
    ...manifestOverrides,
  };
  fs.writeFileSync(path.join(extensionDir, 'build_manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

  const vsixPath = path.join(tempDir, buildVsixFilename(version));
  execFileSync('zip', ['-qr', vsixPath, 'extension'], { cwd: tempDir });
  return { tempDir, vsixPath };
}

test('verifyVsixFile passes on a clean packaged artifact', () => {
  const { vsixPath } = createVsixFixture('0.1.5');
  const result = verifyVsixFile(vsixPath, { expectedVersion: '0.1.5' });
  assert.equal(result.packageJson.version, '0.1.5');
  assert.equal(result.manifest.runtime_mode, 'installed');
});

test('verifyVsixFile fails when the bundled hash does not match the manifest', () => {
  const { vsixPath } = createVsixFixture('0.1.5', { bundle_hash: 'not-the-real-hash' });
  assert.throws(
    () => verifyVsixFile(vsixPath, { expectedVersion: '0.1.5' }),
    /bundle hash mismatch/,
  );
});

test('release naming helpers always move to a new patch version', () => {
  assert.equal(bumpPatchVersion('0.1.4'), '0.1.5');
  assert.equal(buildVsixFilename('0.1.5'), 'aicode-local-agent-0.1.5.vsix');
});
