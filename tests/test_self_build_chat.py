"""Tests for explicit self-build chat routing and execution."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value={}), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        agent = MagicMock()
        agent.generate_code.return_value = "print('ok')"
        agent.evaluate_code.return_value = {"execution_ok": True, "stdout": "ok"}
        mock_agent.return_value = agent
        eng = ChatEngine(str(tmp_path))
    return eng


def test_parse_self_build_phrase_routes_to_self_build(engine):
    req = engine.parse_request("please help build itself in 3 cycles")
    assert req["action"] == "self_build"
    assert req["cycles"] == 3


def test_self_build_handler_returns_action_plan(engine):
    with patch("src.tools.chat_engine.run_self_improvement_cycles") as mock_cycles:
        mock_cycles.return_value = {
            "cycles_requested": 2,
            "cycles_run": 1,
            "target_score": 95.0,
            "converged": False,
            "results": [
                {
                    "cycle": 1,
                    "score": 82.0,
                    "readiness": "in_progress",
                    "actions": [
                        "Implement remaining roadmap items: [40, 46]",
                        "Resolve unknown or invalid dependency licenses.",
                    ],
                }
            ],
        }

        text = engine.execute({"action": "self_build", "cycles": 2})

    assert "Self-Build Cycle Complete" in text
    assert "Latest score: 82.0" in text
    assert "Next Self-Build Actions" in text
    assert "dependency licenses" in text
