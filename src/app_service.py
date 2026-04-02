"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.chat_engine import ChatEngine
from src.tools.commanding import ActionRequest
from src.tools.learning_events import record_output_trace, record_prompt_event


class AppService:
    """Thin service wrapper around the chat engine for app-level entrypoints."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._engine = ChatEngine(str(self.workspace_root), load_context=False)

    def run_request(self, request: ActionRequest, *, source: str = "api") -> dict[str, Any]:
        """Execute a typed request across shared app surfaces."""
        command = request.raw_input or request.action
        response = self._engine.execute_request(request)
        action = response.action or request.action or "unknown"
        confidence = request.confidence
        result_status = response.result_status
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
            source=source,
        )

        output_trace = record_output_trace(
            workspace_root=str(self.workspace_root),
            prompt_event_id=str(prompt_event.get("id", "")),
            applied_preferences=applied_preference_ids,
            tools_used=[action],
            eval_summary=result_status,
        )
        events = [
            {"kind": "command", "message": command},
            {"kind": "route", "message": f"Routed to {action}"},
            {"kind": "result", "message": f"Completed with {result_status}"},
        ]

        return {
            "command": command,
            "action": action,
            "confidence": confidence,
            "response": response.text,
            "applied_preferences": applied_preference_ids,
            "output_trace_id": output_trace.get("output_id"),
            "events": events,
        }

    def run_command(self, command: str, *, source: str = "api") -> dict[str, Any]:
        """Parse and execute a natural-language command."""
        request = self._engine.parse_request_model(command)
        return self.run_request(request, source=source)

    def parse_command(self, command: str) -> ActionRequest:
        """Parse a natural-language command into a typed request without executing it."""
        return self._engine.parse_request_model(command)
