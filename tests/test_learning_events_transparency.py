"""Tests for prompt-event and output-trace transparency logging."""

from src.tools.learning_events import (
    read_output_traces,
    read_prompt_events,
    record_output_trace,
    record_prompt_event,
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
    )
    trace = record_output_trace(
        workspace_root=str(tmp_path),
        prompt_event_id=event["id"],
        applied_preferences=["pref_123"],
        tools_used=["generate"],
        eval_summary="success",
    )

    assert trace["output_id"].startswith("out_")
    rows = read_output_traces(str(tmp_path), limit=5)
    assert rows[-1]["prompt_event_id"] == event["id"]
    assert rows[-1]["applied_preferences"] == ["pref_123"]
