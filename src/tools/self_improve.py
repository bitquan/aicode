from src.tools.project_memory import remember_note
from src.tools.status_report import build_status_report


def _derive_actions(status_report: dict) -> list[str]:
    actions = []

    remaining = status_report.get("roadmap", {}).get("remaining", [])
    if remaining:
        actions.append(f"Implement remaining roadmap items: {remaining}")

    benchmark = status_report.get("benchmark", {})
    for check in benchmark.get("checks", []):
        if not check.get("passed", False):
            actions.append(f"Fix benchmark check failure: {check.get('name', 'unknown')}")

    budgets = status_report.get("budgets", {})
    if not budgets.get("passed", True):
        actions.append("Address budget check failures (time/cost/attempt ceilings).")

    compliance = status_report.get("compliance", {})
    if not compliance.get("license_scan_passed", True):
        actions.append("Resolve unknown or invalid dependency licenses.")
    if not compliance.get("playbooks_ready", True):
        actions.append("Scaffold and complete missing team playbooks.")

    if not actions:
        actions.append("No blocking gaps detected. Run longer soak tests and external benchmarks.")

    return actions


def run_self_improvement_cycles(workspace_root: str, cycles: int = 1, target_score: float = 95.0) -> dict:
    cycles = max(1, int(cycles))
    target_score = float(target_score)

    reports = []
    converged = False

    for index in range(cycles):
        report = build_status_report(workspace_root)
        score = float(report.get("benchmark", {}).get("score", 0.0))
        readiness = report.get("readiness", "in_progress")
        actions = _derive_actions(report)

        remember_note(
            workspace_root,
            key="self_improve_cycle",
            value=f"cycle={index + 1} score={score} readiness={readiness} actions={len(actions)}",
        )

        cycle_result = {
            "cycle": index + 1,
            "score": score,
            "readiness": readiness,
            "actions": actions,
        }
        reports.append(cycle_result)

        if score >= target_score and readiness in {"feature_complete_validation_running", "release_candidate"}:
            converged = True
            break

    return {
        "cycles_requested": cycles,
        "cycles_run": len(reports),
        "target_score": target_score,
        "converged": converged,
        "results": reports,
    }
