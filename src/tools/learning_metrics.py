"""Learning quality metrics harness for baseline evaluation."""

from __future__ import annotations

from typing import Any

from src.tools.learned_preferences import read_correction_events
from src.tools.learning_events import read_output_traces, read_prompt_events
from src.tools.prompt_taxonomy import classify_prompt_type


INTENT_TO_ACTION: dict[str, str] = {
    "greeting": "help_summary",
    "capabilities": "help_summary",
    "repo_summary": "repo_summary",
    "status": "status",
    "search": "search",
    "browse": "browse",
    "generate": "generate",
    "edit": "edit",
    "autofix": "autofix",
    "review": "review",
    "debug": "debug",
    "profile": "profile",
    "coverage": "coverage",
    "security": "security_scan",
    "docs": "doc_generate",
    "api": "api_generate",
    "deps": "dep_resolve",
    "cost": "cost_optimize",
    "learning": "user_learn",
    "analytics": "team_analytics",
}


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _routing_accuracy(prompt_events: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = 0
    correct = 0

    for row in prompt_events:
        prompt = str(row.get("raw_prompt", "")).strip()
        if not prompt:
            continue

        predicted = str(row.get("action_taken", ""))
        taxonomy = classify_prompt_type(prompt)
        expected_intent = taxonomy.get("intent", "unknown")
        expected_action = INTENT_TO_ACTION.get(str(expected_intent), "")
        if not expected_action:
            continue

        eligible += 1
        if predicted == expected_action:
            correct += 1

    return {
        "eligible": eligible,
        "correct": correct,
        "accuracy_pct": _pct(correct, eligible),
    }


def _preference_hit_rate(output_traces: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = 0
    hits = 0

    for row in output_traces:
        tools = [str(item) for item in row.get("tools_used", [])]
        if not any(tool in {"generate", "autofix"} for tool in tools):
            continue
        eligible += 1

        applied = row.get("applied_preferences", [])
        if isinstance(applied, list) and len(applied) > 0:
            hits += 1

    return {
        "eligible": eligible,
        "hits": hits,
        "hit_rate_pct": _pct(hits, eligible),
    }


def _correction_success_rate(corrections: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(corrections)
    success = sum(1 for row in corrections if bool(row.get("applied")))
    return {
        "total": total,
        "successful": success,
        "success_rate_pct": _pct(success, total),
    }


def build_learning_metrics(workspace_root: str, limit: int = 1000) -> dict[str, Any]:
    """Build baseline learning metrics from local telemetry stores."""
    prompt_events = read_prompt_events(workspace_root, limit=limit)
    output_traces = read_output_traces(workspace_root, limit=limit)
    corrections = read_correction_events(workspace_root, limit=limit)

    routing = _routing_accuracy(prompt_events)
    preference_hit = _preference_hit_rate(output_traces)
    correction_success = _correction_success_rate(corrections)

    return {
        "sample_sizes": {
            "prompt_events": len(prompt_events),
            "output_traces": len(output_traces),
            "correction_events": len(corrections),
        },
        "routing_accuracy": routing,
        "preference_hit_rate": preference_hit,
        "correction_success_rate": correction_success,
    }
