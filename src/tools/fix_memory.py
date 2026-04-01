from pathlib import Path
import json
from datetime import datetime, UTC


MEMORY_FILE = ".autofix_reports/fix_memory.jsonl"


def store_fix_memory(workspace_root: str, record: dict):
    root = Path(workspace_root).resolve()
    path = root / MEMORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = {
        "ts": datetime.now(UTC).isoformat(),
        **record,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    return str(path)


def retrieve_similar_fixes(workspace_root: str, target_path: str, failure_category: str, limit: int = 3, strategy: str | None = None) -> list[dict]:
    root = Path(workspace_root).resolve()
    path = root / MEMORY_FILE
    if not path.exists():
        return []

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    scored = []
    for row in rows:
        score = 0
        if row.get("target_path") == target_path:
            score += 3
        if row.get("failure_category") == failure_category:
            score += 3
        if strategy and row.get("strategy") == strategy:
            score += 2
        if row.get("success"):
            score += 2
        if row.get("ts"):
            score += 1
        if score > 0:
            scored.append((score, row.get("ts", ""), row))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in scored[:limit]]
