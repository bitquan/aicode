from pathlib import Path
import re


def plan_repair_files(workspace_root: str, target_path: str, failure: dict) -> list[str]:
    root = Path(workspace_root).resolve()
    planned = [target_path]

    failure_output = failure.get("raw", "")
    traceback_paths = _extract_traceback_paths(failure_output)
    for path in traceback_paths:
        candidate = (root / path).resolve()
        if str(candidate).startswith(str(root)):
            rel = candidate.relative_to(root).as_posix()
            if rel not in planned and candidate.exists():
                planned.append(rel)

    target = (root / target_path).resolve()
    if target.exists() and target_path.startswith("src/"):
        stem = target.stem
        test_candidate = root / "tests" / f"test_{stem}.py"
        if test_candidate.exists():
            rel = test_candidate.relative_to(root).as_posix()
            if rel not in planned:
                planned.append(rel)

    return planned


def _extract_traceback_paths(text: str) -> list[str]:
    matches = re.findall(r'File "([^"]+\.py)"', text)
    normalized = []
    for path in matches:
        if path.startswith("/"):
            continue
        normalized.append(path)
    return normalized
