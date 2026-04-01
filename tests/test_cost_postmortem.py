import json

from src.tools.budget_tracker import record_model_usage
from src.tools.cost_attribution import summarize_costs_by_trace
from src.tools.logger import log_event
from src.tools.postmortem_builder import generate_postmortem_from_blocker


def test_costs_by_trace_groups_metrics(tmp_path):
    record_model_usage(
        str(tmp_path),
        model="demo",
        prompt="hello",
        response="world",
        success=True,
        trace_id="t1",
    )
    record_model_usage(
        str(tmp_path),
        model="demo",
        prompt="a",
        response="b",
        success=True,
        trace_id="t2",
    )
    record_model_usage(
        str(tmp_path),
        model="demo",
        prompt="again",
        response="ok",
        success=True,
        trace_id="t1",
    )

    out = summarize_costs_by_trace(str(tmp_path))
    assert out["trace_count"] == 2
    assert out["traces"][0]["trace_id"] == "t1"
    assert out["traces"][0]["events"] == 2
    assert out["estimated_total_cost_usd"] > 0


def test_postmortem_builder_writes_markdown(tmp_path):
    report_dir = tmp_path / ".autofix_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "trace99.json").write_text(
        json.dumps(
            {
                "target_path": "src/main.py",
                "stop_reason": "max_attempts",
                "attempt_count": 3,
                "failure_categories": ["test_failure"],
                "last_failure": {"summary": "tests still failing"},
            }
        ),
        encoding="utf-8",
    )
    log_event("autofix_start", "trace99", workspace_root=str(tmp_path), target_path="src/main.py")

    out_path = generate_postmortem_from_blocker(str(tmp_path), "trace99")
    text = (tmp_path / "docs" / "playbooks" / "incidents" / "postmortem_trace99.md").read_text(encoding="utf-8")
    assert out_path.endswith("postmortem_trace99.md")
    assert "Postmortem: trace99" in text
    assert "max_attempts" in text