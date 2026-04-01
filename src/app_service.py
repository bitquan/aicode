"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.chat_engine import ChatEngine
from src.tools.learning_events import record_output_trace, record_prompt_event


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
        applied_preferences = self._engine.get_last_applied_preferences()
        applied_preference_ids = [
            pref.get("preference_id", "")
            for pref in applied_preferences
            if pref.get("preference_id")
        ]

        prompt_event = record_prompt_event(
            workspace_root=str(self.workspace_root),
            raw_prompt=command,
            intent=action,
            confidence=float(confidence),
            action_taken=action,
            result_status=result_status,
            source="api",
        )

        output_trace = record_output_trace(
            workspace_root=str(self.workspace_root),
            prompt_event_id=str(prompt_event.get("id", "")),
            applied_preferences=applied_preference_ids,
            tools_used=[action],
            eval_summary=result_status,
        )

        return {
            "command": command,
            "action": action,
            "confidence": confidence,
            "response": response,
            "applied_preferences": applied_preference_ids,
            "output_trace_id": output_trace.get("output_id"),
        }

    def _infer_result_status(self, response: str) -> str:
        text = (response or "").lower()
        if "⚠️" in text or "error" in text or "has issues" in text:
            return "failure"
        if "unable" in text or "partial" in text:
            return "partial"
        return "success"
