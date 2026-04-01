from pathlib import Path


EXCLUDED_DIR_MARKERS = {".git", ".venv", "__pycache__", ".pytest_cache"}


def build_file_index(workspace_root: str, include_ext: tuple[str, ...] = (".py", ".md", ".toml", ".txt")) -> list[dict]:
    root = Path(workspace_root).resolve()
    rows = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(marker in path.parts for marker in EXCLUDED_DIR_MARKERS):
            continue
        if path.suffix.lower() not in include_ext:
            continue
        rel = path.relative_to(root).as_posix()
        rows.append(
            {
                "path": rel,
                "ext": path.suffix.lower(),
                "size": path.stat().st_size,
            }
        )
    return sorted(rows, key=lambda row: row["path"])
