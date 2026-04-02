"""Decision timeline metrics for routing, confidence, and research triggers."""

from __future__ import annotations

from typing import Any

from src.tools.learning_events import read_output_traces, read_prompt_events
from src.tools.live_mode import load_live_mode_state


def _confidence_band(value: float) -> str:
    if value < 0.34:
        return "low"
    if value < 0.66:
        return "medium"
    return "high"


def evaluate_decision_alerts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate decision telemetry summary and return active alert entries."""
    alerts: list[dict[str, Any]] = []

    reroute_rate = float(summary.get("reroute_rate", 0.0) or 0.0)
    low_band = int(summary.get("confidence_bands", {}).get("low", 0) or 0)
    medium_band = int(summary.get("confidence_bands", {}).get("medium", 0) or 0)
    total = int(summary.get("events_considered", 0) or 0)
    low_or_medium_rate = ((low_band + medium_band) / total) if total else 0.0
    research_trigger_rate = float(summary.get("research_trigger_rate", 0.0) or 0.0)

    if reroute_rate >= 0.35:
        alerts.append(
            {
                "code": "high_reroute_rate",
                "severity": "high",
                "message": "Reroute rate is high; routing confidence may be unstable.",
                "value": round(reroute_rate, 3),
            }
        )

    if low_or_medium_rate >= 0.45:
        alerts.append(
            {
                "code": "confidence_drift",
                "severity": "medium",
                "message": "Low/medium confidence decisions are elevated; consider improving prompt routing.",
                "value": round(low_or_medium_rate, 3),
            }
        )

    if research_trigger_rate >= 0.5:
        alerts.append(
            {
                "code": "research_pressure",
                "severity": "medium",
                "message": "Research-trigger rate is high; local knowledge coverage may be insufficient.",
                "value": round(research_trigger_rate, 3),
            }
        )

    return alerts


def build_decision_timeline(workspace_root: str, limit: int = 200) -> dict[str, Any]:
    """Build recent decision timeline and summary aggregates from telemetry stores."""
    sample_limit = max(10, min(int(limit), 2000))
    prompt_events = read_prompt_events(workspace_root, limit=sample_limit)
    output_traces = read_output_traces(workspace_root, limit=sample_limit)
    output_by_prompt_id = {
        str(item.get("prompt_event_id", "")): item
        for item in output_traces
        if str(item.get("prompt_event_id", ""))
    }

    reason_counts: dict[str, int] = {}
    confidence_bands = {"low": 0, "medium": 0, "high": 0}
    reroute_count = 0
    research_trigger_count = 0
    timeline: list[dict[str, Any]] = []

    for event in prompt_events:
        confidence = float(event.get("confidence", 0.0) or 0.0)
        band = _confidence_band(confidence)
        confidence_bands[band] += 1

        needs_external_research = bool(event.get("needs_external_research", False))
        if needs_external_research:
            research_trigger_count += 1
            reason = str(event.get("research_trigger_reason") or "unspecified")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        prompt_id = str(event.get("id", ""))
        trace = output_by_prompt_id.get(prompt_id, {})
        tools_used = [str(item) for item in trace.get("tools_used", []) if str(item).strip()]
        if len(tools_used) > 1:
            reroute_count += 1

        timeline.append(
            {
                "id": prompt_id,
                "timestamp": event.get("timestamp"),
                "raw_prompt": str(event.get("raw_prompt", ""))[:160],
                "action_taken": event.get("action_taken"),
                "confidence": confidence,
                "confidence_band": band,
                "needs_external_research": needs_external_research,
                "research_trigger_reason": event.get("research_trigger_reason"),
                "tools_used": tools_used,
                "result_status": event.get("result_status"),
            }
        )

    total = len(prompt_events)
    sorted_reasons = sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)
    live_state = load_live_mode_state(workspace_root)
    summary = {
        "events_considered": total,
        "research_trigger_count": research_trigger_count,
        "research_trigger_rate": round(research_trigger_count / total, 3) if total else 0.0,
        "reroute_count": reroute_count,
        "reroute_rate": round(reroute_count / total, 3) if total else 0.0,
        "confidence_bands": confidence_bands,
        "top_trigger_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted_reasons[:5]
        ],
        "live_mode_enabled": bool(live_state.get("enabled", False)),
        "live_mode_cycles": int(live_state.get("cycles", 0)),
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

    return {
        "sample_size": total,
        "summary": summary,
        "timeline": timeline,
    }
