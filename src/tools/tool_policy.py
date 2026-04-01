import json
from pathlib import Path


def _policy_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "tool_policy.jsonl"


def record_tool_outcome(workspace_root: str, task_type: str, command: str, success: bool):
    row = {
        "task_type": task_type,
        "command": command,
        "success": bool(success),
    }
    path = _policy_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def recommend_command(workspace_root: str, task_type: str, default_command: str) -> str:
    path = _policy_path(workspace_root)
    if not path.exists():
        return default_command

    scores = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("task_type") != task_type:
            continue
        command = row.get("command")
        if not command:
            continue
        scores.setdefault(command, 0)
        scores[command] += 1 if row.get("success") else -1

    if not scores:
        return default_command
    return max(scores.items(), key=lambda item: item[1])[0]
