"""Application service layer shared by CLI and HTTP API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.tools.chat_engine import ChatEngine
from src.tools.commanding import ActionRequest
from src.tools.learning_events import record_output_trace, record_prompt_event, record_retrieval_trace


class AppService:
    """Thin service wrapper around the chat engine for app-level entrypoints."""

    def __init__(self, workspace_root: str = ".", *, server_process: bool = False):
        self.workspace_root = Path(workspace_root).resolve()
        self._engine = ChatEngine(
            str(self.workspace_root),
            load_context=False,
            server_process=server_process,
        )

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

        response_route_attempts = response.data.get("route_attempts")
        if isinstance(response_route_attempts, list) and response_route_attempts:
            route_attempts = [str(item) for item in response_route_attempts if str(item).strip()]
            if not route_attempts:
                route_attempts = [request.action]

        action = response.action or request.action or "unknown"
        confidence = request.confidence
        result_status = response.result_status
        applied_preferences = self._engine.get_last_applied_preferences()
        applied_preference_ids = [
            pref.get("preference_id", "")
            for pref in applied_preferences
            if pref.get("preference_id")
        ]

        local_context_selected = self._collect_local_context(response.data)
        selected_sources = self._collect_selected_sources(response.data)

        prompt_event = record_prompt_event(
            workspace_root=str(self.workspace_root),
            raw_prompt=command,
            intent=action,
            confidence=float(confidence),
            action_taken=action,
            result_status=result_status,
            source=source,
            needs_external_research=bool(response.data.get("needs_external_research", False)),
            research_trigger_reason=(
                str(response.data.get("research_trigger_reason"))
                if response.data.get("research_trigger_reason") is not None
                else None
            ),
        )

        output_trace = record_output_trace(
            workspace_root=str(self.workspace_root),
            prompt_event_id=str(prompt_event.get("id", "")),
            applied_preferences=applied_preference_ids,
            tools_used=route_attempts,
            verification_summary=result_status,
        )
        retrieval_trace = record_retrieval_trace(
            workspace_root=str(self.workspace_root),
            request_intent=route_attempts[0] if route_attempts else action,
            local_context_selected=local_context_selected,
            research_trigger_reason=(
                str(response.data.get("research_trigger_reason"))
                if response.data.get("research_trigger_reason") is not None
                else None
            ),
            selected_sources=selected_sources,
            selected_preferences=applied_preference_ids,
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
            "pinned_files": response.data.get("pinned_files", []),
            "approved_files": response.data.get("approved_files", []),
            "likely_files": response.data.get("likely_files", []),
            "verification_plan": response.data.get("verification_plan", []),
            "web_research_used": response.data.get("web_research_used"),
            "needs_external_research": response.data.get("needs_external_research", False),
            "research_trigger_reason": response.data.get("research_trigger_reason"),
            "rollback_performed": response.data.get("rollback_performed"),
            "selected_sources": selected_sources,
            "next_step": self._canonical_next_step(
                action=action,
                response_text=response.text,
                response_data=response.data,
            ),
        }

        return {
            "command": command,
            "action": action,
            "confidence": confidence,
            "response": response.text,
            "applied_preferences": applied_preference_ids,
            "output_trace_id": output_trace.get("output_id"),
            "retrieval_trace_id": retrieval_trace.get("trace_id"),
            "route_attempts": route_attempts,
            "recovered_from_action": route_attempts[0] if len(route_attempts) > 1 else None,
            "events": events,
            **response_metadata,
        }

    @staticmethod
    def _canonical_next_step(*, action: str, response_text: str, response_data: dict[str, Any]) -> str:
        """Return one canonical next-step hint for panel/CLI consistency."""
        from_response = str(response_data.get("next_step", "")).strip()
        if from_response:
            return from_response

        lower = response_text.lower()
        marker = "if you want, i can"
        if marker in lower:
            index = lower.find(marker)
            snippet = response_text[index:].strip()
            if snippet:
                first_line = snippet.splitlines()[0].strip()
                if first_line:
                    return first_line

        fallback_by_action = {
            "status": "If you want, I can run a full status validation next.",
            "repo_summary": "If you want, I can drill into architecture, risks, or tests next.",
            "help_summary": "If you want, I can propose one concrete improvement and implement it next.",
            "research": "If you want, I can patch one of the likely files from this research next.",
            "edit": "If you want, I can run targeted verification for this edit next.",
            "autofix": "If you want, I can run a broader regression check next.",
            "self_improve_apply": "If you want, I can verify the applied self-improvement changes next.",
            "readiness": "If you want, I can patch the first failing readiness canary next.",
        }
        return fallback_by_action.get(action, "If you want, I can clarify and take the next step.")

    @staticmethod
    def _collect_local_context(response_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Build a normalized list of local context items used during routing/research."""
        items: list[dict[str, Any]] = []
        likely_files = response_data.get("likely_files", [])
        if isinstance(likely_files, list):
            for entry in likely_files:
                if isinstance(entry, dict):
                    path = str(entry.get("path", "")).strip()
                    reason = str(entry.get("reason", "repo context")).strip() or "repo context"
                    if path:
                        items.append({"path": path, "reason": reason})
                else:
                    path = str(entry).strip()
                    if path:
                        items.append({"path": path, "reason": "repo context"})

        for key, reason in (("pinned_files", "pinned file"), ("approved_files", "approved file")):
            values = response_data.get(key, [])
            if not isinstance(values, list):
                continue
            for entry in values:
                path = str(entry).strip()
                if path and not any(item.get("path") == path for item in items):
                    items.append({"path": path, "reason": reason})
        return items

    @staticmethod
    def _collect_selected_sources(response_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize recorded external sources used during research, if any."""
        raw_sources = response_data.get("selected_sources", [])
        if not isinstance(raw_sources, list):
            return []

        normalized: list[dict[str, Any]] = []
        for source in raw_sources:
            if isinstance(source, dict):
                url = str(source.get("url", "")).strip()
                if not url:
                    continue
                normalized.append(
                    {
                        "label": str(source.get("label", url)).strip() or url,
                        "url": url,
                        "reason": str(source.get("reason", "external research")).strip() or "external research",
                    }
                )
                continue

            url = str(source).strip()
            if url:
                normalized.append({"label": url, "url": url, "reason": "external research"})
        return normalized

    def run_command(self, command: str, *, source: str = "api") -> dict[str, Any]:
        """Parse and execute a natural-language command."""
        request = self._engine.parse_request_model(command)
        return self.run_request(request, source=source)

    def parse_command(self, command: str) -> ActionRequest:
        """Parse a natural-language command into a typed request without executing it."""
        return self._engine.parse_request_model(command)
