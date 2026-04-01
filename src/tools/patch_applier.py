from pathlib import Path
import difflib


def _resolve_target(workspace_root, relative_path):
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Target path must stay inside workspace root.")
    return target


def preview_diff(old_content, new_content, file_label):
    diff_lines = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_label}",
        tofile=f"b/{file_label}",
    )
    return "".join(diff_lines)


def apply_file_edit(workspace_root, relative_path, new_content):
    target = _resolve_target(workspace_root, relative_path)
    existed_before = target.exists()
    old_content = target.read_text(encoding="utf-8") if existed_before else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    return {
        "path": str(target),
        "created": not existed_before,
        "diff": preview_diff(old_content, new_content, relative_path),
    }