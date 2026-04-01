"""Git integration helpers for diff review and commit message suggestions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List


class GitIntegration:
    """Provides safe, read-first git insights for chat workflows."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def status_summary(self) -> Dict:
        code, output = self._run(["git", "status", "--short"])
        if code != 0:
            return {"error": output.strip() or "git status failed"}

        lines = [line for line in output.splitlines() if line.strip()]
        return {
            "changed_files": len(lines),
            "entries": lines,
        }

    def diff_summary(self, max_files: int = 10) -> Dict:
        code, names_output = self._run(["git", "diff", "--name-only"])
        if code != 0:
            return {"error": names_output.strip() or "git diff failed"}

        files = [line.strip() for line in names_output.splitlines() if line.strip()][:max_files]
        summaries: List[Dict] = []

        for file_path in files:
            dcode, diff_output = self._run(["git", "diff", "--", file_path])
            if dcode != 0:
                continue
            added = sum(1 for line in diff_output.splitlines() if line.startswith("+") and not line.startswith("+++"))
            removed = sum(1 for line in diff_output.splitlines() if line.startswith("-") and not line.startswith("---"))
            summaries.append({
                "path": file_path,
                "added": added,
                "removed": removed,
            })

        return {
            "files": summaries,
            "file_count": len(summaries),
        }

    def suggest_commit_message(self) -> Dict:
        diff = self.diff_summary(max_files=8)
        if "error" in diff:
            return diff

        files = diff.get("files", [])
        if not files:
            return {"message": "chore: no changes detected"}

        total_added = sum(item["added"] for item in files)
        total_removed = sum(item["removed"] for item in files)
        top_paths = ", ".join(item["path"] for item in files[:3])

        prefix = "feat"
        if total_removed > total_added:
            prefix = "refactor"
        elif any("test" in item["path"] for item in files):
            prefix = "test"

        return {
            "message": f"{prefix}: update {top_paths}",
            "stats": {
                "files": len(files),
                "added": total_added,
                "removed": total_removed,
            },
        }

    def _run(self, cmd: List[str]) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.returncode, proc.stdout or proc.stderr
        except Exception as exc:
            return 1, str(exc)
