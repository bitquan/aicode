"""Tests for AppService shared app entrypoint logic."""

import json
from unittest.mock import MagicMock, patch

from src.app_service import AppService


@patch("src.app_service.ChatEngine")
def test_run_command_returns_structured_payload(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request.return_value = {"action": "status", "confidence": 0.9}
    engine.execute.return_value = "ok"
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    result = service.run_command("status")

    assert result["command"] == "status"
    assert result["action"] == "status"
    assert result["confidence"] == 0.9
    assert result["response"] == "ok"


@patch("src.app_service.ChatEngine")
def test_run_command_records_prompt_event(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request.return_value = {"action": "help_summary", "confidence": 0.95}
    engine.execute.return_value = "👋 I can help"
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    service.run_command("what is your job?")

    events_path = tmp_path / ".autofix_reports" / "prompt_events.jsonl"
    assert events_path.exists()

    last_row = json.loads(events_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_row["raw_prompt"] == "what is your job?"
    assert last_row["intent"] == "help_summary"
    assert last_row["result_status"] == "success"
