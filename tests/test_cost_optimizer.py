"""Tests for CostOptimizer."""
import json
import pytest
from src.tools.cost_optimizer import CostOptimizer


@pytest.fixture()
def optimizer(tmp_path):
    return CostOptimizer(str(tmp_path))


def _write_metrics(tmp_path, records):
    reports = tmp_path / ".autofix_reports"
    reports.mkdir(exist_ok=True)
    path = reports / "budget_metrics.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))


def test_no_metrics_returns_status(optimizer):
    result = optimizer.analyse()
    assert result["status"] == "NO_DATA"
    assert result["total_cost_usd"] == 0.0
    assert len(result["suggestions"]) > 0


def test_load_metrics_empty(optimizer):
    assert optimizer.load_metrics() == []


def test_analyse_with_metrics(optimizer, tmp_path):
    _write_metrics(tmp_path, [
        {"workflow": "autofix", "cost_usd": 0.001, "input_tokens": 500, "output_tokens": 100},
        {"workflow": "review", "cost_usd": 0.0005, "input_tokens": 300, "output_tokens": 80},
    ])
    result = optimizer.analyse()
    assert result["total_calls"] == 2
    assert result["total_cost_usd"] > 0
    assert result["most_expensive_workflow"] == "autofix"


def test_top_workflows(optimizer, tmp_path):
    _write_metrics(tmp_path, [
        {"workflow": "autofix", "cost_usd": 0.01},
        {"workflow": "autofix", "cost_usd": 0.01},
        {"workflow": "review", "cost_usd": 0.001},
    ])
    top = optimizer.top_workflows_by_cost(top_n=2)
    assert top[0]["workflow"] == "autofix"
    assert top[0]["calls"] == 2


def test_suggestions_present(optimizer, tmp_path):
    _write_metrics(tmp_path, [
        {"workflow": "generate", "cost_usd": 0.02, "input_tokens": 10000, "output_tokens": 100},
    ])
    result = optimizer.analyse()
    assert len(result["suggestions"]) >= 1


def test_over_budget_flag(optimizer, tmp_path):
    reports = tmp_path / ".autofix_reports"
    reports.mkdir(exist_ok=True)
    (reports / "budget_config.json").write_text(json.dumps({"max_daily_cost_usd": 0.001}))
    _write_metrics(tmp_path, [
        {"workflow": "autofix", "cost_usd": 0.01, "input_tokens": 1000, "output_tokens": 200},
    ])
    result = optimizer.analyse()
    assert result["over_budget"] is True
    assert result["status"] == "OVER_BUDGET"
