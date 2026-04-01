"""Diff Visualization helper for summarizing git/unified diffs."""

import re
from pathlib import Path
from typing import Any


_FILE_RE = re.compile(r"^\+\+\+\s+b/(.+)$")


class DiffVisualization:
    """Create compact, visual summaries of text diffs."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def summarize_diff(self, diff_text: str) -> dict[str, Any]:
        """Summarize unified diff by file with add/remove counts."""
        files: dict[str, dict[str, int]] = {}
        current_file = "unknown"

        for line in diff_text.splitlines():
            file_match = _FILE_RE.match(line)
            if file_match:
                current_file = file_match.group(1).strip()
                files.setdefault(current_file, {"added": 0, "removed": 0})
                continue

            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                files.setdefault(current_file, {"added": 0, "removed": 0})
                files[current_file]["added"] += 1
            elif line.startswith("-"):
                files.setdefault(current_file, {"added": 0, "removed": 0})
                files[current_file]["removed"] += 1

        items = []
        total_added = 0
        total_removed = 0
        for file_name, counts in sorted(files.items()):
            total_added += counts["added"]
            total_removed += counts["removed"]
            items.append({"file": file_name, **counts, "visual": self._bar(counts["added"], counts["removed"])})

        return {
            "files_changed": len(items),
            "total_added": total_added,
            "total_removed": total_removed,
            "files": items,
            "status": "OK" if items else "EMPTY",
        }

    def summarize_file(self, diff_file: str) -> dict[str, Any]:
        """Summarize a diff file relative to workspace root."""
        path = self.workspace_root / diff_file
        if not path.exists():
            return {"error": f"File not found: {diff_file}"}
        result = self.summarize_diff(path.read_text(encoding="utf-8"))
        result["file"] = diff_file
        return result

    def _bar(self, added: int, removed: int) -> str:
        add_bar = "+" * min(added, 20)
        rem_bar = "-" * min(removed, 20)
        return f"{add_bar}{rem_bar}" if (add_bar or rem_bar) else "(no changes)"
