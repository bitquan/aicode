"""Audit Trail for chat actions and compliance review."""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class AuditTrail:
    """Persist and query action audit events."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._dir = self.workspace_root / ".audit_trail"
        self._path = self._dir / "actions.jsonl"

    def log_action(
        self,
        action: str,
        actor: str = "chat",
        target: str = "",
        allowed: bool = True,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record one audit event."""
        self._dir.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "actor": actor,
            "action": action,
            "target": target,
            "allowed": bool(allowed),
            "details": details or {},
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
        return event

    def entries(self, limit: int = 50, actor: str | None = None, action: str | None = None) -> dict[str, Any]:
        """Return recent audit events with optional filters."""
        all_events = self._load_events()
        filtered: list[dict[str, Any]] = []
        for event in all_events:
            if actor and event.get("actor") != actor:
                continue
            if action and event.get("action") != action:
                continue
            filtered.append(event)
            if len(filtered) >= limit:
                break

        return {
            "count": len(filtered),
            "entries": filtered,
            "filters": {"actor": actor, "action": action},
        }

    def compliance_summary(self) -> dict[str, Any]:
        """Summarize audit state for compliance checks."""
        events = self._load_events()
        denied = sum(1 for event in events if not event.get("allowed", True))
        allowed = len(events) - denied

        action_counts: dict[str, int] = {}
        for event in events:
            key = str(event.get("action", "unknown"))
            action_counts[key] = action_counts.get(key, 0) + 1

        top_actions = sorted(action_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "total_events": len(events),
            "allowed_events": allowed,
            "denied_events": denied,
            "top_actions": [{"action": a, "count": c} for a, c in top_actions],
            "status": "OK" if denied == 0 else "REVIEW",
        }

    def _load_events(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        events.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return events
