from src.tools.tool_policy import record_tool_outcome, recommend_command


def test_tool_policy_recommend_prefers_success(tmp_path):
    record_tool_outcome(str(tmp_path), "autofix", "python -m pytest -q", True)
    record_tool_outcome(str(tmp_path), "autofix", "python -m pytest -q", True)
    record_tool_outcome(str(tmp_path), "autofix", "python -m pytest -q tests/test_x.py", False)

    out = recommend_command(str(tmp_path), "autofix", "python -m pytest -q")
    assert out == "python -m pytest -q"
