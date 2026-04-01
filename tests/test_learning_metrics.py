"""Tests for baseline learning metrics harness."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine
from src.tools.learned_preferences import add_preference, apply_correction
from src.tools.learning_events import record_output_trace, record_prompt_event
from src.tools.learning_metrics import build_learning_metrics


def test_build_learning_metrics_computes_expected_rates(tmp_path):
    workspace = str(tmp_path)

    ok_event = record_prompt_event(
        workspace_root=workspace,
        raw_prompt="status",
        intent="status",
        confidence=0.95,
        action_taken="status",
        result_status="success",
        source="api",
    )
    record_output_trace(
        workspace_root=workspace,
        prompt_event_id=ok_event["id"],
        applied_preferences=["pref_1"],
        tools_used=["generate"],
        eval_summary="success",
    )

    bad_event = record_prompt_event(
        workspace_root=workspace,
        raw_prompt="what can you tell me about this repo?",
        intent="repo_summary",
        confidence=0.95,
        action_taken="generate",
        result_status="failure",
        source="api",
    )
    record_output_trace(
        workspace_root=workspace,
        prompt_event_id=bad_event["id"],
        applied_preferences=[],
        tools_used=["generate"],
        eval_summary="failure",
    )

    pref = add_preference(workspace, "prefer concise responses", category="output_format")
    apply_correction(
        workspace_root=workspace,
        correction_type="replace",
        correction_text="prefer concise bullet points",
        target_preference_id=pref["preference_id"],
    )

    metrics = build_learning_metrics(workspace, limit=100)
    assert metrics["sample_sizes"]["prompt_events"] == 2
    assert metrics["routing_accuracy"]["eligible"] >= 2
    assert metrics["routing_accuracy"]["accuracy_pct"] == 50.0
    assert metrics["preference_hit_rate"]["hit_rate_pct"] == 50.0
    assert metrics["correction_success_rate"]["success_rate_pct"] == 100.0


@pytest.fixture()
def engine(tmp_path):
    with patch('src.tools.chat_engine.CodingAgent') as mock_agent, \
         patch('src.tools.chat_engine.build_file_index', return_value={}), \
         patch('src.tools.chat_engine.build_status_report', return_value={}):
        mock_agent.return_value = MagicMock()
        eng = ChatEngine(str(tmp_path))
    return eng


def test_chat_parse_learning_metrics_action(engine):
    req = engine.parse_request("learning metrics")
    assert req["action"] == "learning_metrics"


def test_chat_execute_learning_metrics_returns_summary(engine):
    result = engine.execute({"action": "learning_metrics"})
    assert "Learning Metrics Harness" in result
    assert "Routing accuracy" in result
