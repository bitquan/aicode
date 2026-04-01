from src.tools.minimal_repro import write_minimal_repro


def test_write_minimal_repro_creates_file(tmp_path):
    path = write_minimal_repro(
        workspace_root=str(tmp_path),
        trace_id="abc123",
        target_path="src/x.py",
        instruction="fix x",
        test_command="python -m pytest -q",
        last_failure={"category": "syntax", "summary": "bad syntax"},
    )
    content = (tmp_path / ".autofix_reports" / "abc123_repro.md").read_text(encoding="utf-8")
    assert path.endswith("abc123_repro.md")
    assert "bad syntax" in content


def test_write_minimal_repro_includes_pytest_focus(tmp_path):
    write_minimal_repro(
        workspace_root=str(tmp_path),
        trace_id="abc124",
        target_path="src/x.py",
        instruction="fix x",
        test_command="python -m pytest -q",
        last_failure={
            "category": "assertion",
            "summary": "failed",
            "pytest_nodeids": ["tests/test_x.py::test_case"],
        },
    )
    content = (tmp_path / ".autofix_reports" / "abc124_repro.md").read_text(encoding="utf-8")
    assert "Pytest Focused Repro" in content
    assert "tests/test_x.py::test_case" in content
