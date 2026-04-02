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
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': True, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'help_summary'})
    assert isinstance(result, str)
    assert 'I can help' in result
    assert 'vscode-extension/src/extension.ts' in result
    assert 'Web research' in result


def test_parse_self_aware_prompt_maps_to_self_aware_summary(engine):
    req = engine.parse_request('are you self aware?')
    assert req['action'] == 'self_aware_summary'


def test_execute_self_aware_summary_returns_runtime_snapshot(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': False, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status', 'self_aware_summary'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'self_aware_summary'})
    assert 'VS Code panel' in result
    assert 'vscode-extension/src/extension.ts' in result
    assert 'Web research' in result
