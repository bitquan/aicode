"""Custom tool scaffold generator from chat requests."""

import re
from pathlib import Path
from typing import Dict


class ToolBuilder:
    """Generates boilerplate tool modules in `src/tools`."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.tools_dir = self.workspace_root / "src" / "tools"
        self.tests_dir = self.workspace_root / "tests"

    def create_tool(self, name: str, description: str) -> Dict:
        safe_name = self._safe_name(name)
        if not safe_name:
            return {"error": "Invalid tool name"}

        tool_path = self.tools_dir / f"{safe_name}.py"
        test_path = self.tests_dir / f"test_{safe_name}.py"

        if tool_path.exists():
            return {"error": f"Tool already exists: {tool_path.name}"}

        class_name = "".join(part.capitalize() for part in safe_name.split("_"))

        content = f'''"""{description}"""

from typing import Dict


class {class_name}:
    """{description}"""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root

    def run(self, payload: Dict) -> Dict:
        return {{
            "status": "ok",
            "tool": "{safe_name}",
            "payload": payload,
        }}
'''

        test_content = f'''import pytest
from src.tools.{safe_name} import {class_name}


def test_{safe_name}_run():
    tool = {class_name}(".")
    result = tool.run({{"sample": True}})
    assert result["status"] == "ok"
    assert result["tool"] == "{safe_name}"
'''

        tool_path.write_text(content)
        test_path.write_text(test_content)

        return {
            "status": "created",
            "tool": str(tool_path.relative_to(self.workspace_root)),
            "test": str(test_path.relative_to(self.workspace_root)),
        }

    def _safe_name(self, name: str) -> str:
        candidate = name.strip().lower().replace("-", "_").replace(" ", "_")
        candidate = re.sub(r"[^a-z0-9_]", "", candidate)
        candidate = re.sub(r"_+", "_", candidate).strip("_")
        if not candidate or candidate[0].isdigit():
            return ""
        return candidate
