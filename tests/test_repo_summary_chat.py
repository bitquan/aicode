"""Tests for repo summary routing and handler in chat engine."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value=[
             {"path": "src/main.py"},
             {"path": "src/server.py"},
             {"path": "tests/test_api.py"},
         ]), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        mock_agent.return_value = MagicMock()
        eng = ChatEngine(str(tmp_path))
    return eng


def test_parse_repo_summary_prompt(engine):
    req = engine.parse_request("what can you tell me about this repo ?")
    assert req["action"] == "repo_summary"


def test_execute_repo_summary_returns_string(engine):
    result = engine.execute({"action": "repo_summary"})
    assert isinstance(result, str)
    assert "Repository Summary" in result
    assert "Indexed files" in result
