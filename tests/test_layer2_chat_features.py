from unittest.mock import MagicMock, patch

from src.tools.chat_engine import ChatEngine


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_parse_layer2_actions(mock_status, mock_index, mock_agent):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine('.')

    assert engine.parse_request('export knowledge')['action'] == 'knowledge_transfer'
    parsed_import = engine.parse_request('import knowledge knowledge_export.json')
    assert parsed_import['action'] == 'knowledge_transfer'
    assert parsed_import['mode'] == 'import'

    assert engine.parse_request('prompt lab')['action'] == 'prompt_lab'
    assert engine.parse_request('build tool cache helper')['action'] == 'tool_builder'
    assert engine.parse_request('architecture')['action'] == 'architecture'


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_execute_layer2_actions(mock_status, mock_index, mock_agent, tmp_path):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    (tmp_path / 'src' / 'tools').mkdir(parents=True)
    (tmp_path / 'tests').mkdir(parents=True)
    (tmp_path / 'src' / 'main.py').write_text('print("ok")\n')

    engine = ChatEngine(str(tmp_path))

    export_resp = engine.execute({'action': 'knowledge_transfer', 'mode': 'export'})
    assert 'Knowledge exported' in export_resp

    prompt_resp = engine.execute({'action': 'prompt_lab'})
    assert 'Prompt Lab' in prompt_resp

    tool_resp = engine.execute({'action': 'tool_builder', 'name': 'helper_tool'})
    assert 'Tool created' in tool_resp

    arch_resp = engine.execute({'action': 'architecture'})
    assert 'Architecture Analysis' in arch_resp
