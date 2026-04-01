"""Tests for Layer 7 chat_engine integration.

Covers Multi-Language Support and Framework-Specific Experts.
"""

from unittest.mock import MagicMock, patch
import pytest
from src.tools.chat_engine import ChatEngine


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value={}), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        mock_agent.return_value = MagicMock()
        eng = ChatEngine(str(tmp_path))
    return eng


def test_parse_multi_language(engine):
    req = engine.parse_request("language summary src/")
    assert req["action"] == "multi_language"


def test_parse_framework_expert(engine):
    req = engine.parse_request("framework expert fastapi auth")
    assert req["action"] == "framework_expert"


def test_execute_multi_language_returns_string(engine):
    result = engine.execute({"action": "multi_language", "target": "src/"})
    assert isinstance(result, str)


def test_execute_framework_expert_returns_string(engine):
    result = engine.execute({"action": "framework_expert", "task": "fastapi auth patterns"})
    assert isinstance(result, str)
