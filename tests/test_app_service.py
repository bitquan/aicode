"""Tests for AppService shared app entrypoint logic."""

import json
from unittest.mock import MagicMock, patch

from src.app_service import AppService
from src.tools.commanding import ActionRequest, ActionResponse


@patch("src.app_service.ChatEngine")
def test_run_command_returns_structured_payload(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request_model.return_value = ActionRequest(action="status", confidence=0.9, raw_input="status")
    engine.execute_request.return_value = ActionResponse(
        action="status",
        text="ok",
        confidence=0.9,
        result_status="success",
    )
    engine.get_last_applied_preferences.return_value = []
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    result = service.run_command("status")

    assert result["command"] == "status"
    assert result["action"] == "status"
    assert result["confidence"] == 0.9
    assert result["response"] == "ok"
    assert result["applied_preferences"] == []
    assert result["output_trace_id"].startswith("out_")


@patch("src.app_service.ChatEngine")
def test_run_command_records_prompt_event(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request_model.return_value = ActionRequest(
        action="help_summary",
        confidence=0.95,
        raw_input="what is your job?",
    )
    engine.execute_request.return_value = ActionResponse(
        action="help_summary",
        text="👋 I can help",
        confidence=0.95,
        result_status="success",
    )
    engine.get_last_applied_preferences.return_value = []
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    service.run_command("what is your job?")

    events_path = tmp_path / ".autofix_reports" / "prompt_events.jsonl"
    assert events_path.exists()

    last_row = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_row["id"].startswith("evt_")
    assert last_row["raw_prompt"] == "what is your job?"
    assert last_row["intent"] == "help_summary"
    assert last_row["result_status"] == "success"

    traces_path = tmp_path / ".autofix_reports" / "output_traces.jsonl"
    assert traces_path.exists()
    trace_row = json.loads(traces_path.read_text(encoding="utf-8").splitlines()[-1])
    assert trace_row["output_id"].startswith("out_")
    assert trace_row["prompt_event_id"] == last_row["id"]
