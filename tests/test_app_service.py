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
    assert [event["kind"] for event in result["events"]] == ["command", "route", "result"]
    assert result["route_attempts"] == ["status"]
    assert result["recovered_from_action"] is None


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


@patch("src.app_service.ChatEngine")
def test_run_command_recovers_from_edit_misroute(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request_model.return_value = ActionRequest(
        action="edit",
        confidence=0.85,
        raw_input="Add a Clear Chat button to the VS Code panel",
        params={"target": "the VS Code panel", "instruction": "Add a Clear Chat button"},
    )
    engine.execute_request.side_effect = [
        ActionResponse(
            action="edit",
            text="❌ File not found: the VS Code panel",
            confidence=0.85,
            result_status="failure",
        ),
        ActionResponse(
            action="research",
            text="🔎 Research Summary\n  • VS Code panel source: vscode-extension/src/extension.ts",
            confidence=0.88,
            result_status="success",
        ),
    ]
    engine.get_last_applied_preferences.return_value = []
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    result = service.run_command("Add a Clear Chat button to the VS Code panel")

    assert result["action"] == "research"
    assert result["route_attempts"] == ["edit", "research"]
    assert result["recovered_from_action"] == "edit"
    assert [event["kind"] for event in result["events"]] == ["command", "route", "reroute", "route", "result"]


@patch("src.app_service.ChatEngine")
def test_run_command_merges_self_improvement_metadata(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request_model.return_value = ActionRequest(
        action="self_improve_plan",
        confidence=0.96,
        raw_input="self-improve plan add a clear chat button to the VS Code panel",
    )
    engine.execute_request.return_value = ActionResponse(
        action="self_improve_plan",
        text="plan ready",
        confidence=0.96,
        result_status="success",
        data={
            "run_id": "sir_123",
            "mode": "supervised",
            "state": "proposed",
            "goal": "add a clear chat button to the VS Code panel",
            "candidate_summary": "User-requested improvement",
            "likely_files": ["vscode-extension/src/extension.ts"],
            "verification_plan": ["npm --prefix vscode-extension run compile", "Run readiness canaries"],
            "web_research_used": False,
            "rollback_performed": False,
            "events": [{"kind": "state", "message": "Proposal created"}],
        },
    )
    engine.get_last_applied_preferences.return_value = []
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    result = service.run_command("self-improve plan add a clear chat button to the VS Code panel")

    assert result["run_id"] == "sir_123"
    assert result["mode"] == "supervised"
    assert result["state"] == "proposed"
    assert result["likely_files"] == ["vscode-extension/src/extension.ts"]
    assert result["verification_plan"][-1] == "Run readiness canaries"
    assert result["rollback_performed"] is False
    assert any(event["kind"] == "state" for event in result["events"])
