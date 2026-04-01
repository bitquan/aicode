"""Tests for conversational help routing in chat engine."""

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


def test_parse_hey_maps_help_summary(engine):
    req = engine.parse_request('hey')
    assert req['action'] == 'help_summary'


def test_parse_what_can_you_do_maps_help_summary(engine):
    req = engine.parse_request('what can you do ?')
    assert req['action'] == 'help_summary'


def test_parse_what_is_your_job_maps_help_summary(engine):
    req = engine.parse_request('what is your job?')
    assert req['action'] == 'help_summary'


def test_execute_help_summary_returns_capability_text(engine):
    result = engine.execute({'action': 'help_summary'})
    assert isinstance(result, str)
    assert 'I can help' in result
