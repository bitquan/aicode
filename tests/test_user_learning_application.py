"""Tests for automatic application of learned user preferences."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine


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


def test_generate_includes_learned_preferences(engine):
    engine.execute({"action": "user_learn", "lesson": "always run targeted tests first"})

    engine.execute({"action": "generate", "instruction": "write a parser", "stream": False})

    called_instruction = engine.agent.generate_code.call_args[0][0]
    assert "write a parser" in called_instruction
    assert "User Preferences:" in called_instruction
    assert "always run targeted tests first" in called_instruction


def test_no_preferences_keeps_instruction(engine):
    engine.execute({"action": "generate", "instruction": "write hello", "stream": False})
    called_instruction = engine.agent.generate_code.call_args[0][0]
    assert called_instruction == "write hello"
