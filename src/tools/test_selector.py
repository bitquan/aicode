import shlex
from pathlib import Path


def select_test_command(workspace_root: str, target_path: str, default_command: str = "python -m pytest -q") -> str:
    root = Path(workspace_root).resolve()
    target = (root / target_path).resolve()

    rel = target.relative_to(root).as_posix() if str(target).startswith(str(root)) else target_path

    if rel.startswith("tests/") and target.exists():
        return f"python -m pytest -q {shlex.quote(rel)}"

    if rel.startswith("src/") and rel.endswith(".py"):
        stem = Path(rel).stem
        candidate = root / "tests" / f"test_{stem}.py"
        if candidate.exists():
            return f"python -m pytest -q {shlex.quote(candidate.relative_to(root).as_posix())}"

    return default_command
