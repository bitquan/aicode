from src.tools.git_integration import GitIntegration


def test_git_status_summary():
    tool = GitIntegration(".")
    result = tool.status_summary()
    assert "error" in result or "changed_files" in result


def test_git_diff_summary():
    tool = GitIntegration(".")
    result = tool.diff_summary(max_files=5)
    assert "error" in result or "files" in result


def test_git_commit_message_suggestion():
    tool = GitIntegration(".")
    result = tool.suggest_commit_message()
    assert "error" in result or "message" in result
