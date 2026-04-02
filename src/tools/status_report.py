from pathlib import Path
from typing import Literal

from src.tools.benchmark_runner import run_benchmark_suite
from src.tools.budget_tracker import evaluate_budgets, summarize_costs
from src.tools.compliance_summary import build_compliance_summary
from src.tools.decision_timeline import evaluate_decision_alerts
from src.tools.learning_events import read_prompt_events
from src.tools.learning_events import read_output_traces
from src.tools.roadmap_status import get_roadmap_progress

StatusValidationMode = Literal["lightweight", "full"]


def _empty_benchmark_snapshot() -> dict:
    return {
        "profile": "lightweight",
        "score": 0.0,
        "passed": 0,
        "total": 0,
        "checks": [],
        "skipped": True,
    }


def _build_reasoning_snapshot(workspace_root: str, limit: int = 200) -> dict:
    events = read_prompt_events(workspace_root, limit=limit)
    traces = read_output_traces(workspace_root, limit=limit)
    trace_by_prompt_id = {
        str(row.get("prompt_event_id", "")): row
        for row in traces
        if str(row.get("prompt_event_id", ""))
    }
    if not events:
        return {
            "events_considered": 0,
            "avg_confidence": 0.0,
            "low_confidence_threshold": 0.66,
            "low_confidence_count": 0,
            "research_trigger_count": 0,
            "research_trigger_rate": 0.0,
            "reroute_count": 0,
            "reroute_rate": 0.0,
            "confidence_bands": {"low": 0, "medium": 0, "high": 0},
            "alerts": [],
            "highest_alert_severity": "none",
        }

    confidences = [float(event.get("confidence", 0.0) or 0.0) for event in events]
    low_confidence_count = sum(1 for value in confidences if 0.0 < value < 0.66)
    medium_confidence_count = sum(1 for value in confidences if 0.34 <= value < 0.66)
    high_confidence_count = sum(1 for value in confidences if value >= 0.66)
    research_trigger_count = sum(1 for event in events if bool(event.get("needs_external_research", False)))
    reroute_count = 0
    for event in events:
        prompt_id = str(event.get("id", ""))
        trace = trace_by_prompt_id.get(prompt_id, {})
        tools_used = [str(item) for item in trace.get("tools_used", []) if str(item).strip()]
        if len(tools_used) > 1:
            reroute_count += 1

    total = len(events)
    summary = {
        "events_considered": total,
        "avg_confidence": round(sum(confidences) / total, 3),
        "low_confidence_threshold": 0.66,
        "low_confidence_count": low_confidence_count,
        "research_trigger_count": research_trigger_count,
        "research_trigger_rate": round(research_trigger_count / total, 3),
        "reroute_count": reroute_count,
        "reroute_rate": round(reroute_count / total, 3),
        "confidence_bands": {
            "low": total - medium_confidence_count - high_confidence_count,
            "medium": medium_confidence_count,
            "high": high_confidence_count,
        },
    }
    alerts = evaluate_decision_alerts(summary)
    summary["alerts"] = alerts
    summary["highest_alert_severity"] = (
        "high"
        if any(item.get("severity") == "high" for item in alerts)
        else "medium"
        if any(item.get("severity") == "medium" for item in alerts)
        else "none"
    )
    return summary


def build_status_report(workspace_root: str, mode: StatusValidationMode = "full") -> dict:
    roadmap = get_roadmap_progress(workspace_root)
    benchmark = run_benchmark_suite(workspace_root) if mode == "full" else _empty_benchmark_snapshot()
    budgets = evaluate_budgets(workspace_root)
    costs = summarize_costs(workspace_root)
    compliance = build_compliance_summary(workspace_root)
    reasoning = _build_reasoning_snapshot(workspace_root)

    readiness = "validation_deferred" if mode == "lightweight" else "in_progress"
    if roadmap["percent"] >= 100.0 and mode == "lightweight":
        readiness = "feature_complete_validation_deferred"
    if roadmap["percent"] >= 100.0 and mode == "full" and benchmark["score"] >= 80.0:
        readiness = "feature_complete_validation_running"
    if (
        roadmap["percent"] >= 100.0
        and mode == "full"
        and benchmark["score"] >= 95.0
        and budgets["passed"]
        and compliance["license_scan_passed"]
    ):
        readiness = "release_candidate"

    return {
        "validation_mode": mode,
        "readiness": readiness,
        "roadmap": roadmap,
        "benchmark": benchmark,
        "budgets": {
            "passed": budgets["passed"],
            "checks": budgets["checks"],
        },
        "costs": costs,
        "compliance": compliance,
        "reasoning": reasoning,
    }


def export_status_markdown(workspace_root: str, mode: StatusValidationMode = "full") -> str:
    report = build_status_report(workspace_root, mode=mode)
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports" / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "latest_status.md"

    lines = [
        "# Status Report",
        "",
        f"- Validation mode: {report['validation_mode']}",
        f"- Readiness: {report['readiness']}",
        f"- Roadmap completion: {report['roadmap']['completed']}/{report['roadmap']['total']} ({report['roadmap']['percent']}%)",
        f"- Benchmark score: {report['benchmark']['score']}%",
        f"- Budget checks passed: {report['budgets']['passed']}",
        f"- License scan passed: {report['compliance']['license_scan_passed']}",
        f"- Estimated model cost: ${report['costs']['estimated_total_cost_usd']}",
        f"- Avg request confidence: {report['reasoning']['avg_confidence']}",
        f"- Research trigger rate: {report['reasoning']['research_trigger_rate']}",
        f"- Reroute rate: {report['reasoning']['reroute_rate']}",
        f"- Decision alerts: {len(report['reasoning'].get('alerts', []))}",
        "",
        "## Benchmark Checks",
    ]
    for check in report["benchmark"]["checks"]:
        lines.append(f"- {check['name']}: {check['passed']}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
