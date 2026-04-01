"""Tests for Week 2 correction pipeline and scoped preference retrieval."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.chat_engine import ChatEngine
from src.tools.learned_preferences import add_preference, apply_correction, get_preferences, retrieve_preferences


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


def test_preference_persistence_and_scoped_retrieval(tmp_path):
    workspace = str(tmp_path)
    add_preference(workspace, "always run targeted tests first", category="testing")
    add_preference(workspace, "use concise output", category="output_format")

    selected = retrieve_preferences(workspace, request_intent="autofix", top_k=3)
    statements = [row["statement"] for row in selected]
    assert "always run targeted tests first" in statements
    assert all("retrieval_reason" in row for row in selected)


def test_retrieval_deduplicates_statements(tmp_path):
    workspace = str(tmp_path)
    add_preference(workspace, "always run targeted tests first", category="testing", confidence=0.8)
    add_preference(workspace, "always run targeted tests first", category="testing", confidence=0.9)

    selected = retrieve_preferences(workspace, request_intent="generate", top_k=3)
    statements = [row["statement"] for row in selected]
    assert statements.count("always run targeted tests first") == 1


def test_apply_correction_replace_disables_old_and_adds_new(tmp_path):
    workspace = str(tmp_path)
    old = add_preference(workspace, "prefer long explanations", category="output_format")

    result = apply_correction(
        workspace_root=workspace,
        correction_type="replace",
        correction_text="prefer concise responses",
        target_preference_id=old["preference_id"],
    )

    assert result["updated"] is True
    prefs = get_preferences(workspace)
    old_row = next(row for row in prefs if row["preference_id"] == old["preference_id"])
    assert old_row["active"] is False
    assert any(row["statement"] == "prefer concise responses" and row["active"] is True for row in prefs)


def test_chat_correction_updates_following_generate(engine):
    engine.execute({"action": "user_learn", "lesson": "prefer long explanations"})
    result = engine.execute(
        {
            "action": "user_correct",
            "correction_type": "replace",
            "correction_text": "prefer concise responses",
        }
    )
    assert "Preference correction applied" in result

    engine.execute({"action": "generate", "instruction": "write a parser", "stream": False})
    called_instruction = engine.agent.generate_code.call_args[0][0]
    assert "prefer concise responses" in called_instruction
    assert "prefer long explanations" not in called_instruction
