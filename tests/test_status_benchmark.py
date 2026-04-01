from src.tools.benchmark_runner import run_benchmark_suite
from src.tools.roadmap_status import get_roadmap_progress
from src.tools.status_report import build_status_report, export_status_markdown


def test_roadmap_progress_parser(tmp_path):
    (tmp_path / "ROADMAP.md").write_text(
        """
- [x] 1) one
- [ ] 2) two
""".strip(),
        encoding="utf-8",
    )
    out = get_roadmap_progress(str(tmp_path))
    assert out["completed"] == 1
    assert out["total"] == 2
    assert out["remaining"] == [2]


def test_benchmark_suite_with_mocks(monkeypatch, tmp_path):
    monkeypatch.setattr("src.tools.benchmark_runner.run_evaluation_suite", lambda: {"failed": 0})
    monkeypatch.setattr("src.tools.benchmark_runner.run_regression_gate", lambda workspace_root: {"passed": True})
    monkeypatch.setattr("src.tools.benchmark_runner.evaluate_budgets", lambda workspace_root: {"passed": True})
    monkeypatch.setattr("src.tools.benchmark_runner.scan_dependency_licenses", lambda workspace_root: {"passed": True})
    monkeypatch.setattr("src.tools.benchmark_runner.build_compliance_summary", lambda workspace_root: {"license_scan_passed": True, "playbooks_ready": True})
    out = run_benchmark_suite(str(tmp_path))
    assert out["score"] == 100.0


def test_status_report_and_export(monkeypatch, tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- [x] 1) one\n", encoding="utf-8")
    monkeypatch.setattr("src.tools.status_report.run_benchmark_suite", lambda workspace_root: {"score": 100.0, "checks": []})
    monkeypatch.setattr("src.tools.status_report.evaluate_budgets", lambda workspace_root: {"passed": True, "checks": {}})
    monkeypatch.setattr("src.tools.status_report.summarize_costs", lambda workspace_root: {"estimated_total_cost_usd": 0.0})
    monkeypatch.setattr("src.tools.status_report.build_compliance_summary", lambda workspace_root: {"license_scan_passed": True})

    report = build_status_report(str(tmp_path))
    assert report["readiness"] == "release_candidate"

    out_path = export_status_markdown(str(tmp_path))
    assert out_path.endswith("latest_status.md")
