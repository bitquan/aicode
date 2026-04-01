from pathlib import Path
import re


EXCLUDED_DIR_MARKERS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def retrieve_relevant_snippets(workspace_root: str, query: str, limit: int = 5) -> list[dict]:
    root = Path(workspace_root).resolve()
    terms = [term.lower() for term in re.findall(r"[a-zA-Z0-9_]+", query) if len(term) > 1]
    if not terms:
        return []

    results = []
    for path in root.rglob("*.py"):
        if any(marker in path.parts for marker in EXCLUDED_DIR_MARKERS):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        score = sum(lowered.count(term) for term in terms)
        if score <= 0:
            continue
        snippet = text[:1200]
        results.append({"path": rel, "score": score, "snippet": snippet})

    results.sort(key=lambda row: row["score"], reverse=True)
    return results[:limit]
