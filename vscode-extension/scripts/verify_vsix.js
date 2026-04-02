const { verifyCurrentBuild } = require('./build_utils');

try {
  const result = verifyCurrentBuild();
  process.stdout.write(`${JSON.stringify(result.manifest, null, 2)}\n`);
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
  process.exit(1);
}
