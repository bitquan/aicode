"""Tests for Layer 6 chat_engine integration.

Covers Team Knowledge Base, Audit Trail, RBAC, Custom LLM Support,
and Analytics Dashboard command routing + basic handler outputs.
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


def test_parse_team_kb(engine):
    req = engine.parse_request("team kb search auth")
    assert req["action"] == "team_kb"


def test_parse_audit_trail(engine):
    req = engine.parse_request("audit trail")
    assert req["action"] == "audit_trail"


def test_parse_rbac(engine):
    req = engine.parse_request("check role permissions")
    assert req["action"] == "rbac"


def test_parse_custom_llm(engine):
    req = engine.parse_request("model route implement auth")
    assert req["action"] == "custom_llm"


def test_parse_team_analytics(engine):
    req = engine.parse_request("team analytics")
    assert req["action"] == "team_analytics"


def test_execute_team_kb_returns_string(engine):
    result = engine.execute({"action": "team_kb", "query": "auth"})
    assert isinstance(result, str)


def test_execute_audit_trail_returns_string(engine):
    result = engine.execute({"action": "audit_trail"})
    assert isinstance(result, str)


def test_execute_rbac_returns_string(engine):
    result = engine.execute({"action": "rbac", "role": "developer", "permission": "search"})
    assert isinstance(result, str)


def test_execute_custom_llm_returns_string(engine):
    result = engine.execute({"action": "custom_llm", "task": "implement feature"})
    assert isinstance(result, str)


def test_execute_team_analytics_returns_string(engine):
    result = engine.execute({"action": "team_analytics"})
    assert isinstance(result, str)
