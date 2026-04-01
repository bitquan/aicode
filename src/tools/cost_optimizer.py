"""
Cost Optimizer — analyse LLM / API usage recorded by budget_tracker and
surface actionable savings, efficiency improvements, and spend projections.
"""

import json
from pathlib import Path
from typing import Any


class CostOptimizer:
    """Analyse recorded cost metrics and suggest optimisations."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._metrics_path = self.workspace_root / ".autofix_reports" / "budget_metrics.jsonl"
        self._config_path = self.workspace_root / ".autofix_reports" / "budget_config.json"

    # ── Public API ────────────────────────────────────────────────────────────

    def load_metrics(self) -> list[dict]:
        """Return all recorded budget metrics (may be empty)."""
        if not self._metrics_path.exists():
            return []
        records = []
        for line in self._metrics_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def load_config(self) -> dict:
        """Return current budget config, or empty dict."""
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def analyse(self) -> dict[str, Any]:
        """Full cost analysis — aggregates, trends, and suggestions."""
        metrics = self.load_metrics()
        config = self.load_config()

        if not metrics:
            return {
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "suggestions": self._default_suggestions(config),
                "status": "NO_DATA",
                "message": "No cost metrics recorded yet. Make some LLM calls first.",
            }

        agg = self._aggregate(metrics)
        suggestions = self._build_suggestions(agg, config)

        return {
            "total_cost_usd": round(agg["total_cost"], 6),
            "total_calls": agg["calls"],
            "avg_cost_per_call_usd": round(agg["avg_cost"], 6),
            "total_input_tokens": agg["input_tokens"],
            "total_output_tokens": agg["output_tokens"],
            "most_expensive_workflow": agg["top_workflow"],
            "projected_daily_cost_usd": round(agg["projected_daily"], 6),
            "budget_daily_limit_usd": config.get("max_daily_cost_usd", 1.0),
            "over_budget": agg["projected_daily"] > config.get("max_daily_cost_usd", 1.0),
            "suggestions": suggestions,
            "status": "OVER_BUDGET" if agg["projected_daily"] > config.get("max_daily_cost_usd", 1.0) else "WITHIN_BUDGET",
        }

    def top_workflows_by_cost(self, top_n: int = 5) -> list[dict]:
        """Return the *top_n* most expensive workflow types."""
        metrics = self.load_metrics()
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for m in metrics:
            wf = m.get("workflow", "unknown")
            cost = float(m.get("cost_usd", 0.0))
            totals[wf] = totals.get(wf, 0.0) + cost
            counts[wf] = counts.get(wf, 0) + 1
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        return [
            {"workflow": wf, "total_cost_usd": round(cost, 6), "calls": counts[wf]}
            for wf, cost in ranked
        ]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _aggregate(self, metrics: list[dict]) -> dict[str, Any]:
        total_cost = 0.0
        input_tokens = 0
        output_tokens = 0
        workflow_costs: dict[str, float] = {}

        for m in metrics:
            c = float(m.get("cost_usd", 0.0))
            total_cost += c
            input_tokens += int(m.get("input_tokens", 0))
            output_tokens += int(m.get("output_tokens", 0))
            wf = m.get("workflow", "unknown")
            workflow_costs[wf] = workflow_costs.get(wf, 0.0) + c

        calls = len(metrics)
        avg_cost = total_cost / calls if calls else 0.0
        top_wf = max(workflow_costs, key=workflow_costs.get) if workflow_costs else "N/A"
        # Rough projection: assume metrics span ~1 session (~1 hr); extrapolate to 8 hr day
        projected_daily = total_cost * 8.0

        return {
            "total_cost": total_cost,
            "calls": calls,
            "avg_cost": avg_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "top_workflow": top_wf,
            "projected_daily": projected_daily,
            "workflow_costs": workflow_costs,
        }

    def _build_suggestions(self, agg: dict, config: dict) -> list[str]:
        suggestions: list[str] = []
        avg = agg["avg_cost"]
        in_tok = agg["input_tokens"]
        out_tok = agg["output_tokens"]

        if avg > 0.005:
            suggestions.append(
                "Average call cost is high (>${:.4f}). Consider shorter prompts or a cheaper model tier.".format(avg)
            )
        if in_tok > 0 and out_tok > 0 and in_tok / max(out_tok, 1) > 10:
            suggestions.append(
                "Input tokens are >> output tokens. Trim system prompts and context windows to reduce spend."
            )
        if agg["projected_daily"] > config.get("max_daily_cost_usd", 1.0):
            suggestions.append(
                "Projected daily spend exceeds budget limit. Add more aggressive caching or reduce call frequency."
            )
        if agg.get("top_workflow") not in ("N/A", "unknown"):
            suggestions.append(
                f"Workflow '{agg['top_workflow']}' is the largest cost driver. Profile and cache its outputs."
            )
        suggestions.append("Enable prompt caching (if supported) to reuse repeated context across calls.")
        suggestions.append("Batch smaller requests into a single LLM call to amortise per-request overhead.")
        return suggestions

    def _default_suggestions(self, config: dict) -> list[str]:
        return [
            "Track token usage by calling record_metric() after each LLM call.",
            f"Current daily budget cap: USD {config.get('max_daily_cost_usd', 1.0):.2f}.",
            "Enable prompt caching to reduce repeat-call costs.",
            "Use a smaller/cheaper model for low-stakes tasks (review, summarize).",
        ]
