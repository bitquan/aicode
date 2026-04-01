from pathlib import Path

from src.tools.benchmark_runner import run_benchmark_suite
from src.tools.budget_tracker import evaluate_budgets, summarize_costs
from src.tools.compliance_summary import build_compliance_summary
from src.tools.roadmap_status import get_roadmap_progress


def build_status_report(workspace_root: str) -> dict:
    roadmap = get_roadmap_progress(workspace_root)
    benchmark = run_benchmark_suite(workspace_root)
    budgets = evaluate_budgets(workspace_root)
    costs = summarize_costs(workspace_root)
    compliance = build_compliance_summary(workspace_root)

    readiness = "in_progress"
    if roadmap["percent"] >= 100.0 and benchmark["score"] >= 80.0:
        readiness = "feature_complete_validation_running"
    if roadmap["percent"] >= 100.0 and benchmark["score"] >= 95.0 and budgets["passed"] and compliance["license_scan_passed"]:
        readiness = "release_candidate"

    return {
        "readiness": readiness,
        "roadmap": roadmap,
        "benchmark": benchmark,
        "budgets": {
            "passed": budgets["passed"],
            "checks": budgets["checks"],
        },
        "costs": costs,
        "compliance": compliance,
    }


def export_status_markdown(workspace_root: str) -> str:
    report = build_status_report(workspace_root)
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports" / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "latest_status.md"

    lines = [
        "# Status Report",
        "",
        f"- Readiness: {report['readiness']}",
        f"- Roadmap completion: {report['roadmap']['completed']}/{report['roadmap']['total']} ({report['roadmap']['percent']}%)",
        f"- Benchmark score: {report['benchmark']['score']}%",
        f"- Budget checks passed: {report['budgets']['passed']}",
        f"- License scan passed: {report['compliance']['license_scan_passed']}",
        f"- Estimated model cost: ${report['costs']['estimated_total_cost_usd']}",
        "",
        "## Benchmark Checks",
    ]
    for check in report["benchmark"]["checks"]:
        lines.append(f"- {check['name']}: {check['passed']}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
