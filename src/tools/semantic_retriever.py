from pathlib import Path
import re


EXCLUDED_DIR_MARKERS = {".git", ".venv", "__pycache__", ".pytest_cache"}

FAILURE_CATEGORY_HINTS = {
    "syntax": ["def", "class", "return", "import"],
    "dependency": ["import", "requirements", "pyproject", "dependency"],
    "assertion": ["assert", "test_", "pytest"],
    "type": ["typing", "TypeError", "mypy", "annotation"],
    "runtime": ["raise", "exception", "try", "except"],
    "timeout": ["sleep", "timeout", "loop", "retry"],
    "name": ["NameError", "variable", "scope", "global"],
}


def _path_priority_score(path: str, prioritize_paths: list[str] | None) -> int:
    if not prioritize_paths:
        return 0
    score = 0
    for preferred in prioritize_paths:
        preferred = preferred.strip()
        if not preferred:
            continue
        if path == preferred:
            score += 12
        elif path.endswith(preferred):
            score += 8
        elif preferred in path:
            score += 4
    return score


def _failure_hint_score(text: str, failure_category: str | None) -> int:
    if not failure_category:
        return 0
    hints = FAILURE_CATEGORY_HINTS.get(failure_category, [])
    lowered = text.lower()
    return sum(lowered.count(hint.lower()) for hint in hints)


def retrieve_relevant_snippets(
    workspace_root: str,
    query: str,
    limit: int = 5,
    prioritize_paths: list[str] | None = None,
    failure_category: str | None = None,
) -> list[dict]:
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
        lexical_score = sum(lowered.count(term) for term in terms)
        path_score = _path_priority_score(rel, prioritize_paths)
        failure_score = _failure_hint_score(text, failure_category)
        score = lexical_score + path_score + failure_score
        if lexical_score <= 0 and path_score <= 0 and failure_score <= 0:
            continue
        snippet = text[:1200]
        results.append(
            {
                "path": rel,
                "score": score,
                "snippet": snippet,
                "score_detail": {
                    "lexical": lexical_score,
                    "path": path_score,
                    "failure": failure_score,
                },
            }
        )

    results.sort(key=lambda row: row["score"], reverse=True)
    return results[:limit]
