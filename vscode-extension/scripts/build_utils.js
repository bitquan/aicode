const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const EXTENSION_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(EXTENSION_ROOT, '..');
const PACKAGE_JSON_PATH = path.join(EXTENSION_ROOT, 'package.json');
const PACKAGE_LOCK_PATH = path.join(EXTENSION_ROOT, 'package-lock.json');
const OUT_DIR = path.join(EXTENSION_ROOT, 'out');
const DIST_DIR = path.join(EXTENSION_ROOT, 'dist');
const BUILD_MANIFEST_PATH = path.join(EXTENSION_ROOT, 'build_manifest.json');
const MAIN_BUNDLE_PATH = path.join(OUT_DIR, 'extension.js');
const REQUIRED_VSIX_FILES = [
  'extension/package.json',
  'extension/build_manifest.json',
  'extension/out/extension.js',
  'extension/out/runtime_support.js',
  'extension/LICENSE.txt',
  'extension/readme.md',
  'extension/media/aicode.svg',
];

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: EXTENSION_ROOT,
    encoding: 'utf8',
    stdio: 'pipe',
    ...options,
  });
  if (result.status !== 0) {
    const detail = [result.stdout, result.stderr].filter(Boolean).join('\n').trim();
    throw new Error(`${command} ${args.join(' ')} failed${detail ? `:\n${detail}` : ''}`);
  }
  return (result.stdout ?? '').trim();
}

function runInherited(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: EXTENSION_ROOT,
    stdio: 'inherit',
    ...options,
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with exit code ${result.status ?? 'unknown'}`);
  }
}

function resolveLocalBin(name) {
  const suffix = process.platform === 'win32' ? '.cmd' : '';
  return path.join(EXTENSION_ROOT, 'node_modules', '.bin', `${name}${suffix}`);
}

function currentPackageJson() {
  return readJson(PACKAGE_JSON_PATH);
}

function bumpPatchVersion(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(version).trim());
  if (!match) {
    throw new Error(`Unsupported version format: ${version}`);
  }
  return `${match[1]}.${match[2]}.${Number(match[3]) + 1}`;
}

function buildVsixFilename(version) {
  return `aicode-local-agent-${version}.vsix`;
}

function setPackageVersion(version) {
  const pkg = currentPackageJson();
  pkg.version = version;
  writeJson(PACKAGE_JSON_PATH, pkg);

  if (fs.existsSync(PACKAGE_LOCK_PATH)) {
    const lock = readJson(PACKAGE_LOCK_PATH);
    lock.version = version;
    if (lock.packages && lock.packages['']) {
      lock.packages[''].version = version;
    }
    writeJson(PACKAGE_LOCK_PATH, lock);
  }
}

function sha256Buffer(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

function sha256File(filePath) {
  return sha256Buffer(fs.readFileSync(filePath));
}

function currentGitCommit() {
  try {
    return run('git', ['-C', REPO_ROOT, 'rev-parse', '--short=12', 'HEAD']);
  } catch {
    return 'unknown';
  }
}

function buildManifest(runtimeMode) {
  const pkg = currentPackageJson();
  if (!fs.existsSync(MAIN_BUNDLE_PATH)) {
    throw new Error(`Expected compiled bundle at ${MAIN_BUNDLE_PATH}`);
  }
  return {
    version: pkg.version,
    git_commit: currentGitCommit(),
    built_at: new Date().toISOString(),
    bundle_hash: sha256File(MAIN_BUNDLE_PATH),
    runtime_mode: runtimeMode,
  };
}

function writeBuildManifest(runtimeMode) {
  const manifest = buildManifest(runtimeMode);
  fs.writeFileSync(BUILD_MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  return manifest;
}

function compileClean(runtimeMode = 'development-host') {
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.rmSync(BUILD_MANIFEST_PATH, { force: true });
  runInherited(resolveLocalBin('tsc'), ['-p', './']);
  return writeBuildManifest(runtimeMode);
}

function restoreDevelopmentManifestIfPossible() {
  if (fs.existsSync(MAIN_BUNDLE_PATH)) {
    writeBuildManifest('development-host');
  } else {
    fs.rmSync(BUILD_MANIFEST_PATH, { force: true });
  }
}

function withTemporaryPackagedManifest(callback) {
  const previousManifest = fs.existsSync(BUILD_MANIFEST_PATH)
    ? fs.readFileSync(BUILD_MANIFEST_PATH, 'utf8')
    : undefined;
  writeBuildManifest('installed');
  try {
    return callback();
  } finally {
    if (previousManifest === undefined) {
      fs.rmSync(BUILD_MANIFEST_PATH, { force: true });
    } else {
      fs.writeFileSync(BUILD_MANIFEST_PATH, previousManifest, 'utf8');
    }
  }
}

function ensureDistDir() {
  fs.mkdirSync(DIST_DIR, { recursive: true });
}

function packageVsix(outPath) {
  ensureDistDir();
  runInherited('npx', ['--yes', '@vscode/vsce', 'package', '--allow-missing-repository', '--out', outPath]);
  return outPath;
}

function listZipEntries(vsixPath) {
  const output = run('unzip', ['-Z1', vsixPath]);
  return output ? output.split(/\r?\n/).filter(Boolean) : [];
}

function readZipEntry(vsixPath, entryName) {
  const result = spawnSync('unzip', ['-p', vsixPath, entryName], {
    encoding: 'buffer',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  if (result.status !== 0) {
    const stderr = Buffer.isBuffer(result.stderr)
      ? result.stderr.toString('utf8')
      : String(result.stderr ?? '');
    throw new Error(`Could not read ${entryName} from ${vsixPath}: ${stderr.trim()}`);
  }
  return Buffer.from(result.stdout ?? Buffer.alloc(0));
}

function verifyVsixFile(vsixPath, options = {}) {
  const { expectedVersion } = options;
  const entries = listZipEntries(vsixPath);
  for (const required of REQUIRED_VSIX_FILES) {
    if (!entries.includes(required)) {
      throw new Error(`VSIX is missing required file: ${required}`);
    }
  }

  const packageJson = JSON.parse(readZipEntry(vsixPath, 'extension/package.json').toString('utf8'));
  const manifest = JSON.parse(readZipEntry(vsixPath, 'extension/build_manifest.json').toString('utf8'));
  const bundleHash = sha256Buffer(readZipEntry(vsixPath, 'extension/out/extension.js'));

  if (expectedVersion && packageJson.version !== expectedVersion) {
    throw new Error(`VSIX version mismatch: expected ${expectedVersion}, got ${packageJson.version}`);
  }
  if (manifest.version !== packageJson.version) {
    throw new Error(`Build manifest version mismatch: manifest ${manifest.version}, package ${packageJson.version}`);
  }
  if (manifest.runtime_mode !== 'installed') {
    throw new Error(`Build manifest runtime_mode must be "installed", got ${manifest.runtime_mode ?? 'missing'}`);
  }
  if (bundleHash !== manifest.bundle_hash) {
    throw new Error(
      `Build manifest bundle hash mismatch: manifest ${manifest.bundle_hash}, actual ${bundleHash}`,
    );
  }
  for (const field of ['git_commit', 'built_at']) {
    if (typeof manifest[field] !== 'string' || !manifest[field]) {
      throw new Error(`Build manifest field ${field} is missing`);
    }
  }

  return {
    packageJson,
    manifest,
    entries,
  };
}

function verifyCurrentBuild() {
  const version = currentPackageJson().version;
  compileClean('development-host');
  const tempVsix = path.join(os.tmpdir(), `aicode-local-agent-${version}-verify-${process.pid}.vsix`);
  try {
    withTemporaryPackagedManifest(() => packageVsix(tempVsix));
    return verifyVsixFile(tempVsix, { expectedVersion: version });
  } finally {
    fs.rmSync(tempVsix, { force: true });
    restoreDevelopmentManifestIfPossible();
  }
}

function packageRelease() {
  const currentVersion = currentPackageJson().version;
  const nextVersion = bumpPatchVersion(currentVersion);
  setPackageVersion(nextVersion);

  try {
    compileClean('development-host');
    const vsixPath = path.join(DIST_DIR, buildVsixFilename(nextVersion));
    withTemporaryPackagedManifest(() => packageVsix(vsixPath));
    verifyVsixFile(vsixPath, { expectedVersion: nextVersion });
    restoreDevelopmentManifestIfPossible();
    return {
      version: nextVersion,
      vsixPath,
    };
  } catch (error) {
    setPackageVersion(currentVersion);
    restoreDevelopmentManifestIfPossible();
    throw error;
  }
}

function installVsix(vsixPath) {
  verifyVsixFile(vsixPath);
  runInherited('code', ['--install-extension', vsixPath, '--force'], { cwd: REPO_ROOT });
}

module.exports = {
  BUILD_MANIFEST_PATH,
  DIST_DIR,
  EXTENSION_ROOT,
  OUT_DIR,
  REQUIRED_VSIX_FILES,
  buildVsixFilename,
  bumpPatchVersion,
  compileClean,
  currentPackageJson,
  packageRelease,
  packageVsix,
  readZipEntry,
  setPackageVersion,
  sha256Buffer,
  verifyCurrentBuild,
  verifyVsixFile,
  writeBuildManifest,
  withTemporaryPackagedManifest,
  installVsix,
  restoreDevelopmentManifestIfPossible,
};
