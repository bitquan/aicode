"""Tests for Layer 8 chat_engine integration."""

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


def test_parse_architecture_diagram(engine):
    req = engine.parse_request("analyze diagram A->B")
    assert req["action"] == "diagram_analyze"


def test_parse_schema_analyzer(engine):
    req = engine.parse_request("analyze schema")
    assert req["action"] == "schema_analyze"


def test_parse_diff_visualization(engine):
    req = engine.parse_request("visualize diff")
    assert req["action"] == "diff_visualize"


def test_execute_diagram_returns_string(engine):
    result = engine.execute({"action": "diagram_analyze", "diagram": "A->B\nB->C"})
    assert isinstance(result, str)


def test_execute_schema_returns_string(engine):
    result = engine.execute({"action": "schema_analyze", "schema": "CREATE TABLE x (id INT);"})
    assert isinstance(result, str)


def test_execute_diff_returns_string(engine):
    result = engine.execute({"action": "diff_visualize", "diff": "+++ b/x.py\n+line\n-line"})
    assert isinstance(result, str)
