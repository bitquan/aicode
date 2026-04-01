from src.tools.budget_tracker import (
    estimate_cost_usd,
    estimate_tokens,
    evaluate_budgets,
    load_budget_config,
    record_model_usage,
    record_metric,
    set_budget_value,
    summarize_costs,
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


def test_budget_tracker_token_cost_summary(tmp_path):
    assert estimate_tokens("abcd") >= 1
    cost = estimate_cost_usd(str(tmp_path), input_tokens=1000, output_tokens=500)
    assert cost > 0

    record_model_usage(str(tmp_path), model="demo", prompt="hello world", response="ok", success=True)
    summary = summarize_costs(str(tmp_path))
    assert summary["inference_events"] == 1
    assert summary["estimated_total_cost_usd"] > 0
