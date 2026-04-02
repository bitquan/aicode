"""Regression buckets for baseline chat intent routing."""

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


@pytest.mark.parametrize(
    ('prompt', 'expected_action'),
    [
        ('hey', 'help_summary'),
        ('name 5 things you can do ?', 'help_summary'),
        ('whats one improvement you can make ?', 'help_summary'),
        ('talk to me like a human whats one improvement you can make ?', 'help_summary'),
        ('can you improve on how you talk to users ?', 'help_summary'),
        ('what can you tell me about this repo?', 'repo_summary'),
        ('write a function to parse csv', 'generate'),
        ('fix src/main.py', 'autofix'),
        ('Add a Clear Chat button to the VS Code panel', 'research'),
        ('Add recent command history with click-to-replay', 'research'),
        ('review src/server.py', 'review'),
        ('debug src/main.py', 'debug'),
        ('profile src/', 'profile'),
        ('coverage src/', 'coverage'),
        ('security scan src/', 'security_scan'),
        ('generate docs src/main.py', 'doc_generate'),
        ('resolve dependencies', 'dep_resolve'),
        ('readiness', 'readiness'),
        ('status', 'status'),
        ('learning metrics', 'learning_metrics'),
    ],
)
def test_routing_buckets(engine, prompt, expected_action):
    req = engine.parse_request(prompt)
    assert req['action'] == expected_action


def test_unknown_prompt_uses_clarify(engine):
    req = engine.parse_request('hmm maybe something maybe not')
    assert req['action'] == 'clarify'
