from unittest.mock import MagicMock, patch

from src.tools.chat_engine import ChatEngine


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_parse_layer4_actions(mock_status, mock_index, mock_agent):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine('.')

    assert engine.parse_request('collaborate on auth bug')['action'] == 'multi_agent'
    assert engine.parse_request('route task add tests')['action'] == 'agent_route'
    assert engine.parse_request('agent memory auth')['action'] == 'agent_memory'


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_execute_layer4_actions(mock_status, mock_index, mock_agent, tmp_path):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(str(tmp_path))

    response = engine.execute({'action': 'multi_agent', 'task': 'fix auth bug'})
    assert 'Multi-Agent Plan' in response

    response = engine.execute({'action': 'agent_route', 'task': 'write tests'})
    assert 'Primary Agent' in response

    engine.execute({'action': 'agent_memory', 'mode': 'share', 'topic': 'auth', 'note': 'edge case covered'})
    recall = engine.execute({'action': 'agent_memory', 'mode': 'recall', 'topic': 'auth'})
    assert 'Shared Agent Memory' in recall
