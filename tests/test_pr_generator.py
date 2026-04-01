from pathlib import Path

from src.tools.pr_generator import PRGenerator


def test_generate_pr_creates_draft(tmp_path):
    (tmp_path / ".git").mkdir()
    generator = PRGenerator(str(tmp_path))

    # monkeypatch git methods directly for deterministic behavior
    generator.git.status_summary = lambda: {"changed_files": 2, "entries": ["M a.py", "M b.py"]}
    generator.git.diff_summary = lambda max_files=20: {
        "files": [
            {"path": "a.py", "added": 10, "removed": 2},
            {"path": "b.py", "added": 3, "removed": 1},
        ],
        "file_count": 2,
    }
    generator.git.suggest_commit_message = lambda: {"message": "feat: update a.py, b.py"}

    result = generator.generate_pr()
    assert result["status"] == "generated"
    assert result["path"] == "PR_DRAFT.md"
    assert (tmp_path / "PR_DRAFT.md").exists()
