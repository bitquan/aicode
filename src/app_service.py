"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.chat_engine import ChatEngine


class AppService:
    """Thin service wrapper around the chat engine for app-level entrypoints."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._engine = ChatEngine(str(self.workspace_root), load_context=False)

    def run_command(self, command: str) -> dict[str, Any]:
        """Parse and execute a natural-language command."""
        request = self._engine.parse_request(command)
        response = self._engine.execute(request)
        return {
            "command": command,
            "action": request.get("action", "unknown"),
            "confidence": request.get("confidence", 0.0),
            "response": response,
        }
