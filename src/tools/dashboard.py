"""Dashboard data builder for web/API views."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from src.tools.status_report import build_status_report


class DashboardBuilder:
    """Builds dashboard summary payload for UI and API endpoints."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def build(self) -> Dict[str, Any]:
        status = build_status_report(str(self.workspace_root), mode="lightweight")
        roadmap_file = self.workspace_root / "DEVELOPMENT_ROADMAP.md"
        roadmap = self._parse_roadmap(roadmap_file)

        benchmark = status.get("benchmark", {})
        reasoning = status.get("reasoning", {})
        alerts = reasoning.get("alerts", [])
        return {
            "workspace": self.workspace_root.name,
            "readiness": status.get("readiness", "unknown"),
            "validation_mode": status.get("validation_mode", "lightweight"),
            "benchmark_score": benchmark.get("score"),
            "benchmark_profile": benchmark.get("profile"),
            "avg_confidence": reasoning.get("avg_confidence", 0.0),
            "research_trigger_rate": reasoning.get("research_trigger_rate", 0.0),
            "reroute_rate": reasoning.get("reroute_rate", 0.0),
            "decision_alert_count": len(alerts),
            "decision_alert_severity": reasoning.get("highest_alert_severity", "none"),
            "roadmap_percent": roadmap.get("percent", 0.0),
            "roadmap_done": roadmap.get("done", 0),
            "roadmap_total": roadmap.get("total", 0),
        }

    def _parse_roadmap(self, roadmap_file: Path) -> Dict[str, Any]:
        if not roadmap_file.exists():
            return {"percent": 0.0, "done": 0, "total": 0}

        text = roadmap_file.read_text(encoding="utf-8")
        checks = re.findall(r"- \[(x| )\]", text)
        done = sum(1 for state in checks if state == "x")
        total = len(checks)
        percent = round((done / total) * 100, 1) if total else 0.0
        return {"percent": percent, "done": done, "total": total}


def render_dashboard_html(payload: Dict[str, Any]) -> str:
    """Render a minimal HTML dashboard page."""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>aicode Dashboard</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; }}
      .grid {{ display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: 12px; max-width: 880px; }}
      .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; }}
      .title {{ color: #555; font-size: 12px; text-transform: uppercase; }}
      .value {{ font-size: 24px; font-weight: 700; }}
    </style>
  </head>
  <body>
    <h2>aicode Dashboard</h2>
    <div class=\"grid\">
      <div class=\"card\"><div class=\"title\">Workspace</div><div class=\"value\">{payload.get('workspace')}</div></div>
      <div class=\"card\"><div class=\"title\">Readiness</div><div class=\"value\">{payload.get('readiness')}</div></div>
      <div class=\"card\"><div class=\"title\">Validation</div><div class=\"value\">{payload.get('validation_mode')}</div></div>
      <div class=\"card\"><div class=\"title\">Benchmark</div><div class=\"value\">{payload.get('benchmark_score')}</div></div>
        <div class=\"card\"><div class=\"title\">Avg Confidence</div><div class=\"value\">{payload.get('avg_confidence')}</div></div>
        <div class=\"card\"><div class=\"title\">Research Trigger Rate</div><div class=\"value\">{payload.get('research_trigger_rate')}</div></div>
        <div class=\"card\"><div class=\"title\">Reroute Rate</div><div class=\"value\">{payload.get('reroute_rate')}</div></div>
        <div class=\"card\"><div class=\"title\">Decision Alerts</div><div class=\"value\">{payload.get('decision_alert_count')}</div></div>
        <div class=\"card\"><div class=\"title\">Alert Severity</div><div class=\"value\">{payload.get('decision_alert_severity')}</div></div>
      <div class=\"card\"><div class=\"title\">Roadmap</div><div class=\"value\">{payload.get('roadmap_percent')}%</div></div>
      <div class=\"card\"><div class=\"title\">Done</div><div class=\"value\">{payload.get('roadmap_done')}</div></div>
      <div class=\"card\"><div class=\"title\">Total</div><div class=\"value\">{payload.get('roadmap_total')}</div></div>
    </div>
  </body>
</html>
"""
