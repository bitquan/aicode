import json
from pathlib import Path


def _optimizer_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "prompt_optimizer.jsonl"


def choose_prompt_strategy(workspace_root: str, options: list[str], default: str) -> str:
    path = _optimizer_path(workspace_root)
    if not path.exists():
        return default

    scores = {option: 0 for option in options}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        strategy = row.get("strategy")
        if strategy not in scores:
            continue
        scores[strategy] += 1 if row.get("success") else -1
    return max(scores.items(), key=lambda item: item[1])[0]


def record_prompt_outcome(workspace_root: str, strategy: str, success: bool):
    row = {"strategy": strategy, "success": bool(success)}
    path = _optimizer_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row
