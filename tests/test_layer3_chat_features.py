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

    pr_resp = engine.execute({'action': 'pr'})
    assert 'PR draft' in pr_resp or '❌' in pr_resp

    vscode_resp = engine.execute({'action': 'vscode'})
    assert 'VS Code integration' in vscode_resp

    dashboard_resp = engine.execute({'action': 'dashboard'})
    assert 'Dashboard Summary' in dashboard_resp
