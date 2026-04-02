"""Tests for repo summary routing and handler in chat engine."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value=[
             {"path": "src/main.py"},
             {"path": "src/server.py"},
             {"path": "tests/test_api.py"},
         ]), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        mock_agent.return_value = MagicMock()
        eng = ChatEngine(str(tmp_path))
    return eng


def test_parse_repo_summary_prompt(engine):
    req = engine.parse_request("what can you tell me about this repo ?")
    assert req["action"] == "repo_summary"


def test_execute_repo_summary_returns_string(engine):
    result = engine.execute({"action": "repo_summary"})
    assert isinstance(result, str)
    assert "Repository Summary" in result
    assert "Indexed files" in result
    assert "Tell me a goal" in result


def test_execute_status_returns_conversational_summary(engine):
    engine.context.pop("status", None)
    with patch(
        "src.tools.commanding.handlers.repo.build_status_report",
        return_value={
            "validation_mode": "lightweight",
            "readiness": "in_progress",
            "benchmark": {"score": 82.0},
            "roadmap": {"percent": 64.0},
            "reasoning": {
                "avg_confidence": 0.83,
                "reroute_rate": 0.1,
                "research_trigger_rate": 0.2,
                "alerts": [],
                "highest_alert_severity": "none",
            },
        },
    ):
        result = engine.execute({"action": "status", "validation_mode": "lightweight"})

    assert "Project Status" in result
    assert "overall readiness is" in result
    assert "Decision quality" in result
    assert "run a full status validation next" in result


    def test_status_summary_uses_learned_human_style(engine):
        with patch.object(engine, 'prefers_conversational_responses', return_value=True):
            result = engine.execute({'action': 'status'})

        assert 'Quick status:' in result
        assert 'If you want, I can' in result


    def test_repo_summary_uses_learned_human_style(engine):
        with patch.object(engine, 'prefers_conversational_responses', return_value=True):
            result = engine.execute({'action': 'repo_summary'})

        assert 'Quick repo read:' in result
        assert 'If you want, I can next' in result
