from src.tools.eval_runner import run_evaluation_suite


def test_eval_runner_reports_all_checks():
    out = run_evaluation_suite()
    assert out["total"] == 3
    assert out["failed"] == 0
