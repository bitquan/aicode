"""Tests for preference management controls (clear preferences)."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine
from src.tools.learned_preferences import add_preference, clear_preferences, get_preferences


def test_clear_preferences_deactivates_active_rows(tmp_path):
    workspace = str(tmp_path)
    add_preference(workspace, "prefer concise responses", category="output_format")
    add_preference(workspace, "always run tests", category="testing")

    result = clear_preferences(workspace)
    assert result["cleared"] == 2

    active = get_preferences(workspace, active_only=True)
    assert active == []


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value={}), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        agent = MagicMock()
        agent.generate_code.return_value = "print('ok')"
        agent.evaluate_code.return_value = {"execution_ok": True, "stdout": "ok"}
        mock_agent.return_value = agent
        eng = ChatEngine(str(tmp_path))
    return eng


def test_parse_clear_preferences_route(engine):
    req = engine.parse_request("clear learned preferences")
    assert req["action"] == "clear_preferences"


def test_clear_preferences_removes_injection_on_generate(engine):
    engine.execute({"action": "user_learn", "lesson": "prefer concise responses"})
    engine.execute({"action": "clear_preferences"})

    engine.execute({"action": "generate", "instruction": "write parser", "stream": False})
    called_instruction = engine.agent.generate_code.call_args[0][0]
    assert "User Preferences:" not in called_instruction
