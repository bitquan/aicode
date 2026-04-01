"""VS Code integration helpers for editor-context aware workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


class VSCodeIntegration:
    """Provides workspace metadata and launch/task scaffold helpers."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.vscode_dir = self.workspace_root / ".vscode"

    def workspace_snapshot(self) -> Dict:
        py_files = list(self.workspace_root.glob("src/**/*.py"))
        test_files = list(self.workspace_root.glob("tests/**/*.py"))
        return {
            "workspace": self.workspace_root.name,
            "python_files": len(py_files),
            "test_files": len(test_files),
            "has_vscode_dir": self.vscode_dir.exists(),
        }

    def ensure_tasks(self) -> Dict:
        self.vscode_dir.mkdir(exist_ok=True)
        tasks_path = self.vscode_dir / "tasks.json"
        if tasks_path.exists():
            return {"status": "exists", "path": ".vscode/tasks.json"}

        tasks_path.write_text(
            """{
  \"version\": \"2.0.0\",
  \"tasks\": [
    {
      \"label\": \"aicode: test\",
      \"type\": \"shell\",
      \"command\": \"python -m pytest -q\",
      \"group\": \"test\"
    },
    {
      \"label\": \"aicode: chat\",
      \"type\": \"shell\",
      \"command\": \"python -m src.main chat\"
    }
  ]
}
""",
            encoding="utf-8",
        )
        return {"status": "created", "path": ".vscode/tasks.json"}

    def ensure_launch(self) -> Dict:
        self.vscode_dir.mkdir(exist_ok=True)
        launch_path = self.vscode_dir / "launch.json"
        if launch_path.exists():
            return {"status": "exists", "path": ".vscode/launch.json"}

        launch_path.write_text(
            """{
  \"version\": \"0.2.0\",
  \"configurations\": [
    {
      \"name\": \"Python: aicode chat\",
      \"type\": \"python\",
      \"request\": \"launch\",
      \"module\": \"src.main\",
      \"args\": [\"chat\"],
      \"justMyCode\": true
    }
  ]
}
""",
            encoding="utf-8",
        )
        return {"status": "created", "path": ".vscode/launch.json"}
