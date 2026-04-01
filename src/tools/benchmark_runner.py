from src.tools.budget_tracker import evaluate_budgets
from src.tools.compliance_summary import build_compliance_summary
from src.tools.eval_runner import run_evaluation_suite
from src.tools.gate_runner import run_regression_gate
from src.tools.license_scanner import scan_dependency_licenses


def run_benchmark_suite(workspace_root: str) -> dict:
    checks = []

    eval_report = run_evaluation_suite()
    checks.append({"name": "eval_suite", "passed": eval_report["failed"] == 0})

    gate_report = run_regression_gate(workspace_root=workspace_root)
    checks.append({"name": "regression_gate", "passed": bool(gate_report["passed"])})

    budget_report = evaluate_budgets(workspace_root)
    checks.append({"name": "budget_checks", "passed": bool(budget_report["passed"])})

    license_report = scan_dependency_licenses(workspace_root)
    checks.append({"name": "license_scan", "passed": bool(license_report["passed"])})

    compliance_report = build_compliance_summary(workspace_root)
    checks.append({"name": "compliance_summary", "passed": bool(compliance_report["license_scan_passed"] and compliance_report["playbooks_ready"])})

    passed = sum(1 for row in checks if row["passed"])
    total = len(checks)
    score = round((passed / total) * 100, 1) if total else 0.0
    return {
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
    }
