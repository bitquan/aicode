from unittest.mock import MagicMock, patch

from src.tools.chat_engine import ChatEngine


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_parse_layer3_actions(mock_status, mock_index, mock_agent):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine('.')

    assert engine.parse_request('git status')['action'] == 'git'
    assert engine.parse_request('generate pr')['action'] == 'pr'
    assert engine.parse_request('vscode setup')['action'] == 'vscode'
    assert engine.parse_request('dashboard')['action'] == 'dashboard'


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_execute_layer3_actions(mock_status, mock_index, mock_agent, tmp_path):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    (tmp_path / 'src' / 'tools').mkdir(parents=True)
    (tmp_path / 'tests').mkdir(parents=True)
    (tmp_path / 'src' / 'main.py').write_text('print("ok")\n')
    (tmp_path / 'DEVELOPMENT_ROADMAP.md').write_text('- [x] done\n')

    engine = ChatEngine(str(tmp_path))

    git_resp = engine.execute({'action': 'git', 'query': 'git status'})
    assert 'Git status' in git_resp or 'changed file' in git_resp or '❌' in git_resp
    assert 'I checked your working tree' in git_resp or '❌' in git_resp

    pr_resp = engine.execute({'action': 'pr'})
    assert 'PR draft' in pr_resp or '❌' in pr_resp

    vscode_resp = engine.execute({'action': 'vscode'})
    assert 'VS Code integration' in vscode_resp

    dashboard_resp = engine.execute({'action': 'dashboard'})
    assert 'Dashboard Summary' in dashboard_resp
    assert 'latest project snapshot' in dashboard_resp


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
@patch('src.tools.commanding.handlers.repo.run_engine_readiness_suite')
def test_execute_readiness_conversational_output(mock_readiness, mock_status, mock_index, mock_agent):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    mock_readiness.return_value = {
        'status': 'pass',
        'passed': 3,
        'total': 3,
        'failed': 0,
        'routing_generation': 4,
        'readiness_suite_version': 1,
        'server_reachable': True,
        'ollama_reachable': True,
        'web_enabled': True,
        'known_vscode_panel': 'vscode-extension/src/extension.ts',
        'results': [
            {
                'name': 'repo_summary_route',
                'passed': True,
                'actual_action': 'repo_summary',
                'expected_action': 'repo_summary',
                'missing_response_markers': [],
            }
        ],
    }

    engine = ChatEngine('.')
    with patch.object(engine, 'prefers_conversational_responses', return_value=False):
        readiness_resp = engine.execute({'action': 'readiness'})

    assert 'Self-Improvement Readiness' in readiness_resp
    assert 'Current status:' in readiness_resp
    assert 'Recent canaries:' in readiness_resp
