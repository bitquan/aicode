from pathlib import Path


def build_doc_update(workspace_root: str, changed_files: list[str] | None = None) -> str:
    root = Path(workspace_root).resolve()
    files = changed_files or []
    if not files:
        files = []
        for path in root.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if rel.startswith("src/"):
                files.append(rel)
            if len(files) >= 8:
                break

    lines = ["## Suggested Documentation Update", "", "### Changed Areas"]
    lines.extend([f"- {path}" for path in files])
    lines.append("")
    lines.append("### Notes")
    lines.append("- Update README command examples for newly added workflows.")
    lines.append("- Add a changelog bullet for safety/repair improvements.")
    return "\n".join(lines)
