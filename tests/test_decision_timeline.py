"""Tests for decision timeline metrics."""

from src.tools.decision_timeline import build_decision_timeline
from src.tools.learning_events import record_output_trace, record_prompt_event


def test_build_decision_timeline_includes_summary_and_timeline(tmp_path):
    workspace = str(tmp_path)

    evt1 = record_prompt_event(
        workspace_root=workspace,
        raw_prompt="what changed in latest fastapi release",
        intent="research",
        confidence=0.65,
        action_taken="research",
        result_status="success",
        source="cli",
        needs_external_research=True,
        research_trigger_reason="freshness_sensitive_query",
    )
    evt2 = record_prompt_event(
        workspace_root=workspace,
        raw_prompt="status",
        intent="status",
        confidence=0.95,
        action_taken="status",
        result_status="success",
        source="cli",
        needs_external_research=False,
        research_trigger_reason=None,
    )

    record_output_trace(
        workspace_root=workspace,
        prompt_event_id=evt1["id"],
        applied_preferences=[],
        tools_used=["generate", "research"],
        eval_summary="success",
    )
    record_output_trace(
        workspace_root=workspace,
        prompt_event_id=evt2["id"],
        applied_preferences=[],
        tools_used=["status"],
        eval_summary="success",
    )

    timeline = build_decision_timeline(workspace, limit=50)

    assert timeline["sample_size"] == 2
    assert timeline["summary"]["research_trigger_count"] == 1
    assert timeline["summary"]["reroute_count"] == 1
    assert timeline["summary"]["confidence_bands"]["high"] >= 1
    assert len(timeline["timeline"]) == 2
