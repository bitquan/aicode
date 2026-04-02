"""Tests for prompt-event and output-trace transparency logging."""

from src.tools.learning_events import (
    read_output_traces,
    read_prompt_events,
    read_retrieval_traces,
    record_output_trace,
    record_prompt_event,
    record_retrieval_trace,
)


def test_prompt_event_has_id_and_can_be_read(tmp_path):
    row = record_prompt_event(
        workspace_root=str(tmp_path),
        raw_prompt="status",
        intent="status",
        confidence=0.9,
        action_taken="status",
        result_status="success",
        source="api",
        needs_external_research=False,
        research_trigger_reason=None,
    )
    assert row["id"].startswith("evt_")

    rows = read_prompt_events(str(tmp_path), limit=5)
    assert rows[-1]["id"] == row["id"]


def test_output_trace_can_be_recorded_and_read(tmp_path):
    event = record_prompt_event(
        workspace_root=str(tmp_path),
        raw_prompt="write parser",
        intent="generate",
        confidence=0.65,
        action_taken="generate",
        result_status="success",
        source="api",
        needs_external_research=True,
        research_trigger_reason="low_confidence_unknown",
    )
    trace = record_output_trace(
        workspace_root=str(tmp_path),
        prompt_event_id=event["id"],
        applied_preferences=["pref_123"],
        tools_used=["generate"],
        verification_summary="success",
    )

    assert trace["output_id"].startswith("out_")
    rows = read_output_traces(str(tmp_path), limit=5)
    assert rows[-1]["prompt_event_id"] == event["id"]
    assert rows[-1]["applied_preferences"] == ["pref_123"]
    assert rows[-1]["verification_summary"] == "success"
    assert rows[-1]["eval_summary"] == "success"
    event_rows = read_prompt_events(str(tmp_path), limit=5)
    assert event_rows[-1]["needs_external_research"] is True
    assert event_rows[-1]["research_trigger_reason"] == "low_confidence_unknown"


def test_retrieval_trace_can_be_recorded_and_read(tmp_path):
    trace = record_retrieval_trace(
        workspace_root=str(tmp_path),
        request_intent="research",
        local_context_selected=[{"path": "src/server.py", "reason": "repo match"}],
        research_trigger_reason="freshness_sensitive_query",
        selected_sources=[{"label": "fastapi docs", "url": "https://fastapi.tiangolo.com/", "reason": "official project documentation"}],
        selected_preferences=["pref_123"],
    )

    assert trace["trace_id"].startswith("rtv_")
    rows = read_retrieval_traces(str(tmp_path), limit=5)
    assert rows[-1]["request_intent"] == "research"
    assert rows[-1]["local_context_selected"][0]["path"] == "src/server.py"
    assert rows[-1]["selected_sources"][0]["url"] == "https://fastapi.tiangolo.com/"
    assert rows[-1]["selected_preferences"] == ["pref_123"]
