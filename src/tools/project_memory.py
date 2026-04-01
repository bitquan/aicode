import json
from pathlib import Path


def _memory_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "project_memory.jsonl"


def remember_note(workspace_root: str, key: str, value: str):
    row = {"key": key, "value": value}
    path = _memory_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def get_notes(workspace_root: str, key: str | None = None, limit: int = 20) -> list[dict]:
    path = _memory_path(workspace_root)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if key and item.get("key") != key:
            continue
        rows.append(item)
    return rows[-limit:]


def search_notes(workspace_root: str, query: str, limit: int = 10) -> list[dict]:
    query_l = query.lower()
    rows = get_notes(workspace_root, key=None, limit=500)
    scored = []
    for row in rows:
        text = f"{row.get('key', '')} {row.get('value', '')}".lower()
        score = text.count(query_l)
        if score > 0:
            scored.append({"score": score, **row})
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]
