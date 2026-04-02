"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

import re
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

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        candidate = value.strip().strip("`'\"")
        if not candidate:
            return False
        if "/" in candidate or candidate.startswith((".", "src", "tests", "vscode-extension", ".vscode")):
            return True
        return bool(re.search(r"\.[a-z0-9]{1,8}$", candidate.lower()))

    @classmethod
    def _recoverable_fallback(cls, request: ActionRequest, response_text: str) -> tuple[str, str] | None:
        text = (response_text or "").lower()

        if request.action == "edit" and "file not found:" in text:
            target = str(request.get("target", ""))
            if target and not cls._looks_like_path(target) and request.raw_input:
                return ("research", "Recovered from edit misroute after non-path target lookup failed.")

        if request.action == "clarify":
            raw = (request.raw_input or request.get("original_input", "") or "").strip()
            normalized = raw.lower().strip()
            for prefix in ("please ", "can you ", "could you ", "would you "):
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix):].strip()
            if normalized.startswith(("add ", "build ", "create ", "implement ", "support ", "make ", "improve ")):
                return ("research", "Recovered from low-confidence clarification by running repo research first.")

        return None

    def run_request(self, request: ActionRequest, *, source: str = "api") -> dict[str, Any]:
        """Execute a typed request across shared app surfaces."""
        command = request.raw_input or request.action
        response = self._engine.execute_request(request)
        route_attempts = [request.action]
        recovery_note = ""

        fallback = self._recoverable_fallback(request, response.text)
        if fallback:
            fallback_action, recovery_note = fallback
            fallback_request = ActionRequest(
                action=fallback_action,
                confidence=max(float(request.confidence), 0.8),
                raw_input=command,
                params={
                    "goal": command,
                    "original_action": request.action,
                    "recovery_reason": recovery_note,
                },
            )
            response = self._engine.execute_request(fallback_request)
            request = fallback_request
            route_attempts.append(fallback_request.action)

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
            tools_used=route_attempts,
            eval_summary=result_status,
        )
        events = [
            {"kind": "command", "message": command},
            {"kind": "route", "message": f"Routed to {route_attempts[0]}"},
        ]
        if len(route_attempts) > 1:
            events.append({"kind": "reroute", "message": recovery_note or f"Recovered to {action}"})
            events.append({"kind": "route", "message": f"Recovered to {action}"})
        for event in response.data.get("events", []):
            kind = str(event.get("kind", "")).strip()
            message = str(event.get("message", "")).strip()
            if kind and message:
                events.append({"kind": kind, "message": message})
        events.append({"kind": "result", "message": f"Completed with {result_status}"})

        response_metadata = {
            "run_id": response.data.get("run_id"),
            "mode": response.data.get("mode"),
            "state": response.data.get("state"),
            "goal": response.data.get("goal"),
            "candidate_summary": response.data.get("candidate_summary"),
            "likely_files": response.data.get("likely_files", []),
            "verification_plan": response.data.get("verification_plan", []),
            "web_research_used": response.data.get("web_research_used"),
            "rollback_performed": response.data.get("rollback_performed"),
        }

        return {
            "command": command,
            "action": action,
            "confidence": confidence,
            "response": response.text,
            "applied_preferences": applied_preference_ids,
            "output_trace_id": output_trace.get("output_id"),
            "route_attempts": route_attempts,
            "recovered_from_action": route_attempts[0] if len(route_attempts) > 1 else None,
            "events": events,
            **response_metadata,
        }

    def run_command(self, command: str, *, source: str = "api") -> dict[str, Any]:
        """Parse and execute a natural-language command."""
        request = self._engine.parse_request_model(command)
        return self.run_request(request, source=source)

    def parse_command(self, command: str) -> ActionRequest:
        """Parse a natural-language command into a typed request without executing it."""
        return self._engine.parse_request_model(command)
