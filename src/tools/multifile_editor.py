from pathlib import Path

from src.tools.patch_applier import apply_file_edit, preview_diff


def apply_multifile_rewrites(agent, workspace_root: str, target_files: list[str], instruction: str) -> dict:
    root = Path(workspace_root).resolve()
    applied = []
    skipped = []

    for rel_path in target_files:
        absolute = (root / rel_path).resolve()
        if not str(absolute).startswith(str(root)) or not absolute.exists():
            skipped.append({"path": rel_path, "reason": "missing_or_outside_workspace"})
            continue

        current = absolute.read_text(encoding="utf-8")
        updated = agent.rewrite_file(rel_path, instruction, current)
        diff = preview_diff(current, updated, rel_path)
        if not diff:
            skipped.append({"path": rel_path, "reason": "no_changes"})
            continue

        result = apply_file_edit(workspace_root, rel_path, updated)
        applied.append({"path": rel_path, "diff": result["diff"]})

    return {"applied": applied, "skipped": skipped}
