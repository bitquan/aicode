"""Automated PR description generator from repository changes."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.tools.git_integration import GitIntegration


class PRGenerator:
    """Builds PR-ready markdown content and saves draft files."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.git = GitIntegration(str(self.workspace_root))

    def generate_pr(self, title: str | None = None) -> Dict:
        status = self.git.status_summary()
        if "error" in status:
            return status

        diff = self.git.diff_summary(max_files=20)
        if "error" in diff:
            return diff

        commit_hint = self.git.suggest_commit_message().get("message", "feat: update project")
        pr_title = title or commit_hint.replace(":", "", 1).strip().capitalize()

        changed_files = [item["path"] for item in diff.get("files", [])]
        markdown = self._render_markdown(pr_title, changed_files, diff)

        output = self.workspace_root / "PR_DRAFT.md"
        output.write_text(markdown, encoding="utf-8")

        return {
            "status": "generated",
            "title": pr_title,
            "path": str(output.relative_to(self.workspace_root)),
            "changed_files": len(changed_files),
        }

    def _render_markdown(self, title: str, changed_files: List[str], diff: Dict) -> str:
        top = [
            f"# {title}",
            "",
            "## Summary",
            "- Generated automatically from git working tree changes.",
            "- Please review for correctness before opening the PR.",
            "",
            "## Changed Files",
        ]

        if changed_files:
            for path in changed_files:
                top.append(f"- {path}")
        else:
            top.append("- No changed files detected")

        top.extend([
            "",
            "## Diff Stats",
        ])

        for item in diff.get("files", [])[:25]:
            top.append(f"- {item['path']}: +{item['added']} / -{item['removed']}")

        top.extend([
            "",
            "## Checklist",
            "- [ ] Tests pass locally",
            "- [ ] Backward compatibility reviewed",
            "- [ ] Documentation updated if needed",
        ])

        return "\n".join(top) + "\n"
