from time import perf_counter

from src.tools.budget_tracker import evaluate_budgets, record_metric
from src.tools.eval_runner import run_evaluation_suite
from src.tools.license_scanner import scan_dependency_licenses
from src.tools.test_runner import run_test_command


def run_regression_gate(
    test_command: str = "python -m pytest -q",
    workspace_root: str = ".",
    profile: str = "standard",
) -> dict:
    start = perf_counter()
    tests = run_test_command(test_command, cwd=workspace_root)
    evals = run_evaluation_suite()
    budgets = evaluate_budgets(workspace_root)
    licenses = scan_dependency_licenses(workspace_root)
    duration = perf_counter() - start

    passed = bool(tests.get("success")) and evals.get("failed", 1) == 0
    strict_requirements = {
        "budgets_passed": bool(budgets.get("passed", False)),
        "licenses_passed": bool(licenses.get("passed", False)),
    }
    if profile == "strict":
        passed = passed and all(strict_requirements.values())

    record_metric(
        workspace_root=workspace_root,
        workflow="gate",
        duration_seconds=duration,
        success=passed,
    )
    return {
        "passed": passed,
        "profile": profile,
        "test_command": test_command,
        "duration_seconds": round(duration, 4),
        "tests": tests,
        "eval": evals,
        "strict_requirements": strict_requirements,
    }
