"""Tests for AppService shared app entrypoint logic."""

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
