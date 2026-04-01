"""Tests for user-driven learning input in chat engine."""

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


def test_parse_learn_prefix_maps_user_learn(engine):
    req = engine.parse_request('learn: always validate API health first')
    assert req['action'] == 'user_learn'
    assert 'validate API health' in req['lesson']


def test_parse_teach_prefix_maps_user_learn(engine):
    req = engine.parse_request('teach: keep prompts concise')
    assert req['action'] == 'user_learn'


def test_parse_correction_prefix_maps_user_correct(engine):
    req = engine.parse_request('correction: prefer concise responses')
    assert req['action'] == 'user_correct'
    assert req['correction_type'] == 'replace'


def test_execute_user_learn_persists_and_responds(engine):
    result = engine.execute({'action': 'user_learn', 'lesson': 'always run targeted tests first'})
    assert isinstance(result, str)
    assert 'Learned from your input' in result

    kb = engine.team_knowledge_base.search('targeted tests')
    assert kb['count'] >= 1
