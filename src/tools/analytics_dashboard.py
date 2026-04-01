"""Analytics dashboard metrics for team productivity and quality trends."""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class AnalyticsDashboard:
    """Build simple analytics snapshots from project telemetry sources."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._audit_path = self.workspace_root / ".audit_trail" / "actions.jsonl"
        self._kb_path = self.workspace_root / ".team_knowledge" / "knowledge.jsonl"
        self._budget_path = self.workspace_root / ".autofix_reports" / "budget_metrics.jsonl"

    def generate(self) -> dict[str, Any]:
        """Generate combined productivity and quality analytics."""
        audit = self._load_jsonl(self._audit_path)
        kb = self._load_jsonl(self._kb_path)
        budget = self._load_jsonl(self._budget_path)

        productivity = self._productivity_metrics(audit, kb)
        quality = self._quality_metrics(audit)
        cost = self._cost_metrics(budget)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "productivity": productivity,
            "quality": quality,
            "cost": cost,
            "status": "OK",
        }

    def _productivity_metrics(self, audit: list[dict], kb: list[dict]) -> dict[str, Any]:
        by_actor: dict[str, int] = {}
        for event in audit:
            actor = str(event.get("actor", "unknown"))
            by_actor[actor] = by_actor.get(actor, 0) + 1

        return {
            "audit_events": len(audit),
            "knowledge_entries": len(kb),
            "active_actors": len(by_actor),
            "top_actors": sorted(by_actor.items(), key=lambda kv: kv[1], reverse=True)[:5],
        }

    def _quality_metrics(self, audit: list[dict]) -> dict[str, Any]:
        denied = sum(1 for event in audit if not event.get("allowed", True))
        total = len(audit)
        compliance_rate = 1.0 if total == 0 else round((total - denied) / total, 4)
        action_counts: dict[str, int] = {}
        for event in audit:
            action = str(event.get("action", "unknown"))
            action_counts[action] = action_counts.get(action, 0) + 1

        return {
            "denied_actions": denied,
            "compliance_rate": compliance_rate,
            "top_actions": sorted(action_counts.items(), key=lambda kv: kv[1], reverse=True)[:5],
        }

    def _cost_metrics(self, budget_metrics: list[dict]) -> dict[str, Any]:
        total_cost = sum(float(item.get("cost_usd", 0.0)) for item in budget_metrics)
        total_calls = len(budget_metrics)
        avg_cost = 0.0 if total_calls == 0 else round(total_cost / total_calls, 6)
        return {
            "total_cost_usd": round(total_cost, 6),
            "total_calls": total_calls,
            "avg_cost_per_call_usd": avg_cost,
        }

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
