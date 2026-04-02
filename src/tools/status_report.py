from pathlib import Path
from typing import Literal

from src.tools.benchmark_runner import run_benchmark_suite
from src.tools.budget_tracker import evaluate_budgets, summarize_costs
from src.tools.compliance_summary import build_compliance_summary
from src.tools.roadmap_status import get_roadmap_progress

StatusValidationMode = Literal["lightweight", "full"]


def _empty_benchmark_snapshot() -> dict:
    return {
        "profile": "lightweight",
        "score": 0.0,
        "passed": 0,
        "total": 0,
        "checks": [],
        "skipped": True,
    }


def build_status_report(workspace_root: str, mode: StatusValidationMode = "full") -> dict:
    roadmap = get_roadmap_progress(workspace_root)
    benchmark = run_benchmark_suite(workspace_root) if mode == "full" else _empty_benchmark_snapshot()
    budgets = evaluate_budgets(workspace_root)
    costs = summarize_costs(workspace_root)
    compliance = build_compliance_summary(workspace_root)

    readiness = "validation_deferred" if mode == "lightweight" else "in_progress"
    if roadmap["percent"] >= 100.0 and mode == "lightweight":
        readiness = "feature_complete_validation_deferred"
    if roadmap["percent"] >= 100.0 and mode == "full" and benchmark["score"] >= 80.0:
        readiness = "feature_complete_validation_running"
    if (
        roadmap["percent"] >= 100.0
        and mode == "full"
        and benchmark["score"] >= 95.0
        and budgets["passed"]
        and compliance["license_scan_passed"]
    ):
        readiness = "release_candidate"

    return {
        "validation_mode": mode,
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


def export_status_markdown(workspace_root: str, mode: StatusValidationMode = "full") -> str:
    report = build_status_report(workspace_root, mode=mode)
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports" / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "latest_status.md"

    lines = [
        "# Status Report",
        "",
        f"- Validation mode: {report['validation_mode']}",
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
