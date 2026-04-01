import re
from pathlib import Path


def get_roadmap_progress(workspace_root: str) -> dict:
    root = Path(workspace_root).resolve()
    roadmap = root / "ROADMAP.md"
    if not roadmap.exists():
        return {"completed": 0, "total": 0, "percent": 0.0, "remaining": []}

    text = roadmap.read_text(encoding="utf-8")
    items = re.findall(r"- \[( |x)\] (\d+)\)", text)
    completed = sum(1 for state, _ in items if state == "x")
    total = len(items)
    remaining = [int(number) for state, number in items if state != "x"]
    percent = round((completed / total) * 100, 1) if total else 0.0
    return {
        "completed": completed,
        "total": total,
        "percent": percent,
        "remaining": remaining,
    }
