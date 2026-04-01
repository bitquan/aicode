"""Tests for AnalyticsDashboard."""

import json
from src.tools.analytics_dashboard import AnalyticsDashboard


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_generate_empty_metrics(tmp_path):
    dashboard = AnalyticsDashboard(str(tmp_path))
    report = dashboard.generate()
    assert report["status"] == "OK"
    assert report["productivity"]["audit_events"] == 0


def test_generate_with_data(tmp_path):
    _write_jsonl(
        tmp_path / ".audit_trail" / "actions.jsonl",
        [
            {"actor": "alice", "action": "edit", "allowed": True},
            {"actor": "bob", "action": "deploy", "allowed": False},
        ],
    )
    _write_jsonl(
        tmp_path / ".team_knowledge" / "knowledge.jsonl",
        [{"author": "alice", "topic": "auth", "note": "rotate keys"}],
    )
    _write_jsonl(
        tmp_path / ".autofix_reports" / "budget_metrics.jsonl",
        [{"cost_usd": 0.002}, {"cost_usd": 0.001}],
    )

    dashboard = AnalyticsDashboard(str(tmp_path))
    report = dashboard.generate()
    assert report["productivity"]["audit_events"] == 2
    assert report["quality"]["denied_actions"] == 1
    assert report["cost"]["total_cost_usd"] == 0.003


def test_compliance_rate(tmp_path):
    _write_jsonl(
        tmp_path / ".audit_trail" / "actions.jsonl",
        [{"actor": "a", "action": "x", "allowed": True}, {"actor": "b", "action": "y", "allowed": False}],
    )
    dashboard = AnalyticsDashboard(str(tmp_path))
    report = dashboard.generate()
    assert report["quality"]["compliance_rate"] == 0.5
