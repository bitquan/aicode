from src.tools.eval_runner import run_evaluation_suite
from src.tools.test_runner import run_test_command


def run_regression_gate(test_command: str = "python -m pytest -q") -> dict:
    tests = run_test_command(test_command)
    evals = run_evaluation_suite()
    passed = bool(tests.get("success")) and evals.get("failed", 1) == 0
    return {
        "passed": passed,
        "test_command": test_command,
        "tests": tests,
        "eval": evals,
    }
