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


def test_parse_name_5_things_maps_help_summary(engine):
    req = engine.parse_request('name 5 things you can do ?')
    assert req['action'] == 'help_summary'


def test_parse_talk_improvement_maps_help_summary(engine):
    req = engine.parse_request('can you improve on how you talk to users ?')
    assert req['action'] == 'help_summary'


def test_parse_one_improvement_prompt_maps_help_summary(engine):
    req = engine.parse_request('whats one improvement you can make ?')
    assert req['action'] == 'help_summary'


def test_parse_human_improvement_prompt_maps_help_summary(engine):
    req = engine.parse_request('talk to me like a human whats one improvement you can make ?')
    assert req['action'] == 'help_summary'


def test_execute_help_summary_returns_capability_text(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': True, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'confidence_policy': {'low_confidence_research_threshold': 0.66},
        'recent_decision_metrics': {
            'reroute_rate': 0.2,
            'research_trigger_rate': 0.3,
            'alerts': [{'severity': 'high', 'message': 'surge'}],
            'highest_alert_severity': 'high',
        },
        'self_improvement': {'mode': 'supervised', 'latest_run_id': None},
        'commands': ['generate', 'research', 'status'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'help_summary'})
    assert isinstance(result, str)
    assert 'repo-focused coding partner' in result
    assert 'vscode-extension/src/extension.ts' in result
    assert 'Web research' in result
    assert 'Top actions' in result


def test_execute_help_summary_for_five_items_prompt(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': True, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'help_summary', 'raw_input': 'name 5 things you can do ?'})

    assert 'Here are 5 things I can do' in result
    assert 'Tell me one target file' in result


def test_execute_help_summary_for_talk_improvement_prompt(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': True, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'help_summary', 'raw_input': 'can you improve on how you talk to users ?'})

    assert 'Absolutely' in result
    assert 'concise summary' in result


def test_parse_affirmative_followup_adopts_help_style_preference(engine):
    engine.context['last_response_action'] = 'help_summary'
    engine.context['last_response_text'] = (
        'Absolutely — and I can start now. '\
        'If you want, I can use this response style by default: concise summary, concrete change, and clear next step.'
    )

    req = engine.parse_request_model('yes do that')

    assert req.action == 'user_learn'
    assert 'Prefer concise, human, next-step-oriented responses by default.' == req.params['lesson']


def test_help_summary_uses_learned_human_style(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': False, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status', 'review', 'autofix', 'browse'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot), \
         patch.object(engine, 'prefers_conversational_responses', return_value=True):
        result = engine.execute({'action': 'help_summary'})

    assert 'I can help with the real work' in result
    assert 'Best next step' in result


def test_parse_self_aware_prompt_maps_to_self_aware_summary(engine):
    req = engine.parse_request('are you self aware?')
    assert req['action'] == 'self_aware_summary'


def test_parse_self_improve_plan_prompt_maps_to_self_improve_plan(engine):
    req = engine.parse_request('self-improve plan add a clear chat button to the VS Code panel')
    assert req['action'] == 'self_improve_plan'
    assert req['goal'] == 'add a clear chat button to the VS Code panel'


def test_parse_self_improve_apply_prompt_maps_to_self_improve_apply(engine):
    req = engine.parse_request('approve self-improve sir_123')
    assert req['action'] == 'self_improve_apply'
    assert req['run_id'] == 'sir_123'


def test_parse_self_improve_status_prompt_maps_to_self_improve_status(engine):
    req = engine.parse_request('self-improve status')
    assert req['action'] == 'self_improve_status'


def test_execute_self_aware_summary_returns_runtime_snapshot(engine):
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'editable_surfaces': ['src/server.py', 'vscode-extension/src/extension.ts'],
        'server': {'reachable': False, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'summary': 'enabled (optional; explicit requests only)'},
        'confidence_policy': {'low_confidence_research_threshold': 0.66},
        'recent_decision_metrics': {
            'avg_confidence': 0.8,
            'reroute_rate': 0.25,
            'research_trigger_rate': 0.4,
            'alerts': [{'severity': 'medium', 'message': 'trend'}],
            'highest_alert_severity': 'medium',
        },
        'self_improvement': {
            'mode': 'supervised',
            'latest_run_id': 'sir_latest',
            'latest_state': 'proposed',
            'last_accepted_run': None,
            'last_rollback_reason': None,
        },
        'commands': ['generate', 'research', 'status', 'self_aware_summary'],
    }
    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot):
        result = engine.execute({'action': 'self_aware_summary'})
    assert 'VS Code panel' in result
    assert 'vscode-extension/src/extension.ts' in result
    assert 'Web research' in result
    assert 'Recent reroute rate' in result
    assert 'Decision alerts' in result
    assert 'Self-improvement mode' in result
