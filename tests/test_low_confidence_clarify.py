"""Tests for low-confidence clarification flow in chat routing."""

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


def test_parse_actionable_prompt_routes_to_research(engine):
    req = engine.parse_request('please make this better')
    assert req['action'] == 'research'
    assert req['confidence'] >= 0.7


def test_parse_clear_code_prompt_routes_to_generate(engine):
    req = engine.parse_request('implement a python function for fibonacci')
    assert req['action'] == 'generate'
    assert req.get('stream') is True


def test_execute_clarify_returns_followup_prompt(engine):
    result = engine.execute({'action': 'clarify', 'original_input': 'not sure what to do'})
    assert 'route this correctly' in result
    assert 'generate code' in result
    assert 'research' in result
