"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.chat_engine import ChatEngine
from src.tools.learning_events import record_prompt_event


class AppService:
    """Thin service wrapper around the chat engine for app-level entrypoints."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._engine = ChatEngine(str(self.workspace_root), load_context=False)

    def run_command(self, command: str) -> dict[str, Any]:
        """Parse and execute a natural-language command."""
        request = self._engine.parse_request(command)
        response = self._engine.execute(request)
        action = request.get("action", "unknown")
        confidence = request.get("confidence", 0.0)
        result_status = self._infer_result_status(response)

        record_prompt_event(
            workspace_root=str(self.workspace_root),
            raw_prompt=command,
            intent=action,
            confidence=float(confidence),
            action_taken=action,
            result_status=result_status,
            source="api",
        )

        return {
            "command": command,
            "action": action,
            "confidence": confidence,
            "response": response,
        }

    def _infer_result_status(self, response: str) -> str:
        text = (response or "").lower()
        if "⚠️" in text or "error" in text or "has issues" in text:
            return "failure"
        if "unable" in text or "partial" in text:
            return "partial"
        return "success"
