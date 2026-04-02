const path = require('node:path');

const { installVsix, packageRelease } = require('./build_utils');

function resolveVsixArgument() {
  const arg = process.argv[2];
  if (!arg) {
    return undefined;
  }
  return path.isAbsolute(arg) ? arg : path.resolve(process.cwd(), arg);
}

try {
  const existingVsix = resolveVsixArgument();
  const vsixPath = existingVsix ?? packageRelease().vsixPath;
  installVsix(vsixPath);
  process.stdout.write(`${vsixPath}\n`);
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
  process.exit(1);
}
