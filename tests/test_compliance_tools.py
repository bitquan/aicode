from src.tools.compliance_summary import build_compliance_summary
from src.tools.license_scanner import scan_dependency_licenses
from src.tools.playbook_manager import get_playbook_status, scaffold_playbooks


def test_license_scanner_marks_unknown(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "demo"

[tool.poetry.dependencies]
python = "^3.11"
unknownlib = "^1"
""".strip(),
        encoding="utf-8",
    )
    out = scan_dependency_licenses(str(tmp_path))
    assert out["passed"] is False
    assert out["unknown_count"] == 1


def test_license_scanner_project_license_fallback(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "demo"
license = "mit"

[tool.poetry.dependencies]
python = "^3.11"
unknownlib = "^1"
""".strip(),
        encoding="utf-8",
    )
    out = scan_dependency_licenses(str(tmp_path))
    assert out["project_license"] == "MIT"
    assert out["passed"] is True


def test_playbook_scaffold_and_status(tmp_path):
    result = scaffold_playbooks(str(tmp_path))
    assert result["created"]
    status = get_playbook_status(str(tmp_path))
    assert all(status.values())


def test_compliance_summary(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "demo"

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2"
""".strip(),
        encoding="utf-8",
    )
    scaffold_playbooks(str(tmp_path))
    summary = build_compliance_summary(str(tmp_path))
    assert summary["runtime_dep_count"] == 1
    assert summary["playbooks_ready"] is True
    assert "budget_checks_passed" in summary
