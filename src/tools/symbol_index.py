from pathlib import Path
import ast


EXCLUDED_DIR_MARKERS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def build_symbol_index(workspace_root: str) -> list[dict]:
    root = Path(workspace_root).resolve()
    symbols = []
    for path in root.rglob("*.py"):
        if any(marker in path.parts for marker in EXCLUDED_DIR_MARKERS):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append({"kind": "function", "name": node.name, "path": rel, "line": node.lineno})
            elif isinstance(node, ast.ClassDef):
                symbols.append({"kind": "class", "name": node.name, "path": rel, "line": node.lineno})
    return sorted(symbols, key=lambda row: (row["path"], row["line"]))
