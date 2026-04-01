from src.tools.audit_export import export_audit_markdown
from src.tools.gate_runner import run_regression_gate
from src.tools.logger import log_event
from src.tools.release_notes import generate_release_notes
from src.tools.telemetry import summarize_telemetry


def test_gate_runner_passes(monkeypatch):
    monkeypatch.setattr("src.tools.gate_runner.run_test_command", lambda command: {"success": True, "stdout": "", "stderr": "", "returncode": 0, "timed_out": False})
    monkeypatch.setattr("src.tools.gate_runner.run_evaluation_suite", lambda: {"failed": 0, "checks": [], "total": 0, "passed": 0})
    out = run_regression_gate("python -m pytest -q")
    assert out["passed"] is True


def test_telemetry_and_release_notes(tmp_path):
    log_event("autofix_start", "abc123", workspace_root=str(tmp_path), target_path="src/main.py")
    summary = summarize_telemetry(str(tmp_path))
    assert summary["traces"] == 1
    notes = generate_release_notes(str(tmp_path), "0.2.0")
    assert "Release 0.2.0" in notes


def test_audit_export_writes_markdown(tmp_path):
    log_event("autofix_start", "xyz999", workspace_root=str(tmp_path), target_path="src/main.py")
    out_path = export_audit_markdown(str(tmp_path), "xyz999")
    text = (tmp_path / ".autofix_reports" / "exports" / "xyz999.md").read_text(encoding="utf-8")
    assert out_path.endswith("xyz999.md")
    assert "Audit Export: xyz999" in text
