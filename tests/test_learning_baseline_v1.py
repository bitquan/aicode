"""High-level acceptance checks for Main Baseline v1."""

from unittest.mock import MagicMock, patch

import pytest

from src.app_service import AppService
from src.tools.chat_engine import ChatEngine
from src.tools.commanding import ActionRequest


@pytest.fixture()
def engine(tmp_path):
    with patch("src.tools.chat_engine.CodingAgent") as mock_agent, \
         patch("src.tools.chat_engine.build_file_index", return_value={}), \
         patch("src.tools.chat_engine.build_status_report", return_value={}):
        agent = MagicMock()
        agent.generate_code.return_value = "print('ok')"
        agent.evaluate_code.return_value = {"execution_ok": True, "stdout": "ok"}
        mock_agent.return_value = agent
        eng = ChatEngine(str(tmp_path))
    return eng


def test_baseline_help_prompt_routes_to_help_summary(engine):
    request = engine.parse_request("what can you do now?")
    assert request["action"] == "help_summary"


def test_baseline_repo_prompt_routes_to_repo_summary(engine):
    request = engine.parse_request("what can you tell me about this repo?")
    assert request["action"] == "repo_summary"


def test_baseline_latest_query_triggers_research(engine):
    engine.capabilities["web_policy"] = {"enabled": True, "requires_explicit_request": True}

    with patch.object(
        engine.dispatcher,
        "dispatch",
        return_value=MagicMock(
            action="research",
            text="research summary",
            confidence=0.8,
            result_status="success",
            data={},
        ),
    ) as mock_dispatch:
        response = engine.execute_request(
            ActionRequest(
                action="clarify",
                confidence=0.3,
                raw_input="what changed in latest fastapi release",
            )
        )

    dispatched_request = mock_dispatch.call_args.args[1]
    assert dispatched_request.action == "research"
    assert response.data["needs_external_research"] is True
    assert response.data["research_trigger_reason"] in {"low_confidence_unknown", "freshness_sensitive_query"}


def test_baseline_teach_apply_correct_loop(engine):
    engine.execute({"action": "user_learn", "lesson": "prefer long explanations"})
    engine.execute(
        {
            "action": "user_correct",
            "correction_type": "replace",
            "correction_text": "prefer concise responses",
        }
    )

    engine.execute({"action": "generate", "instruction": "write a parser", "stream": False})
    called_instruction = engine.agent.generate_code.call_args[0][0]
    assert "prefer concise responses" in called_instruction
    assert "prefer long explanations" not in called_instruction


@patch("src.app_service.ChatEngine")
def test_baseline_app_command_returns_trace_artifacts(mock_chat_engine, tmp_path):
    engine = MagicMock()
    engine.parse_request_model.return_value = ActionRequest(action="status", confidence=0.9, raw_input="status")
    engine.execute_request.return_value = MagicMock(
        action="status",
        text="ok",
        confidence=0.9,
        result_status="success",
        data={},
    )
    engine.get_last_applied_preferences.return_value = []
    mock_chat_engine.return_value = engine

    service = AppService(str(tmp_path))
    result = service.run_command("status")

    assert result["output_trace_id"].startswith("out_")
    assert result["retrieval_trace_id"].startswith("rtv_")
