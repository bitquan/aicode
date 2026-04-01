from src.tools.budget_tracker import (
    evaluate_budgets,
    load_budget_config,
    record_metric,
    set_budget_value,
)


def test_budget_tracker_roundtrip(tmp_path):
    config = load_budget_config(str(tmp_path))
    assert "max_gate_seconds" in config

    set_budget_value(str(tmp_path), "max_gate_seconds", 1.0)
    record_metric(str(tmp_path), workflow="gate", duration_seconds=0.5, success=True)
    out = evaluate_budgets(str(tmp_path))
    assert out["checks"]["gate_duration_ok"] is True


def test_budget_tracker_detects_over_budget(tmp_path):
    set_budget_value(str(tmp_path), "max_autofix_attempts", 1)
    record_metric(str(tmp_path), workflow="autofix", duration_seconds=2.0, success=False, attempts=3)
    out = evaluate_budgets(str(tmp_path))
    assert out["checks"]["autofix_attempts_ok"] is False
