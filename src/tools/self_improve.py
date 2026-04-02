"""Self-improvement controller, runtime history, and legacy score cycles."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.tools.learning_events import read_output_traces, read_prompt_events
from src.tools.patch_applier import apply_file_edit, preview_diff
from src.tools.project_memory import remember_note
from src.tools.readiness_suite import run_engine_readiness_suite
from src.tools.research_support import build_research_payload, build_verification_plan
from src.tools.snapshot_manager import rollback_snapshot
from src.tools.status_report import build_status_report
from src.tools.test_runner import run_test_command

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


SELF_IMPROVEMENT_MODE = "supervised"
MAX_EDIT_FILES = 3
MAX_CHANGED_LINES = 200
RUN_HISTORY_LIMIT = 50
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "requirements-dev.txt",
}
DISALLOWED_PATH_MARKERS = {
    "migrations",
    "alembic",
}
KNOWN_FILE_NAMES = {
    "readme",
    "readme.md",
    "package.json",
    "pyproject.toml",
    "tasks.json",
    "launch.json",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _runtime_dir(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    runtime_dir = root / ".knowledge_base"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def _runs_path(workspace_root: str) -> Path:
    return _runtime_dir(workspace_root) / "self_improve_runs.json"


def _load_runs(workspace_root: str) -> list[dict[str, Any]]:
    path = _runs_path(workspace_root)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _save_runs(workspace_root: str, runs: list[dict[str, Any]]) -> None:
    path = _runs_path(workspace_root)
    trimmed = runs[-RUN_HISTORY_LIMIT:]
    path.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")


def _find_run(runs: list[dict[str, Any]], run_id: str) -> dict[str, Any] | None:
    for run in runs:
        if run.get("run_id") == run_id:
            return run
    return None


def _append_event(run: dict[str, Any], kind: str, message: str) -> None:
    run.setdefault("events", []).append(
        {
            "kind": kind,
            "message": message,
            "timestamp": _utc_now_iso(),
        }
    )


def list_self_improvement_runs(workspace_root: str) -> list[dict[str, Any]]:
    return _load_runs(workspace_root)


def get_self_improvement_run(workspace_root: str, run_id: str) -> dict[str, Any] | None:
    return _find_run(_load_runs(workspace_root), run_id)


def get_latest_self_improvement_run(workspace_root: str) -> dict[str, Any] | None:
    runs = _load_runs(workspace_root)
    return runs[-1] if runs else None


def build_self_improvement_status_snapshot(workspace_root: str) -> dict[str, Any]:
    runs = _load_runs(workspace_root)
    latest = runs[-1] if runs else None
    accepted = next((item for item in reversed(runs) if item.get("state") == "verified"), None)
    rolled_back = next((item for item in reversed(runs) if item.get("state") == "rolled_back"), None)
    return {
        "mode": SELF_IMPROVEMENT_MODE,
        "latest_run_id": latest.get("run_id") if latest else None,
        "latest_state": latest.get("state") if latest else None,
        "last_accepted_run": accepted.get("run_id") if accepted else None,
        "last_rollback_reason": rolled_back.get("last_error") if rolled_back else None,
        "run_count": len(runs),
    }


def _normalize_path_token(token: str) -> str:
    return token.strip().strip("`'\"()[]{}.,:;")


def _looks_like_explicit_path(token: str) -> bool:
    candidate = _normalize_path_token(token)
    if not candidate:
        return False
    lowered = candidate.lower()
    if "/" in candidate or candidate.startswith((".", "src", "tests", "vscode-extension", ".vscode")):
        return True
    if re.search(r"\.[a-z0-9]{1,8}$", lowered):
        return True
    return lowered in KNOWN_FILE_NAMES


def _extract_explicit_paths(goal: str) -> list[str]:
    matches = re.findall(
        r"`[^`]+`|(?:\.{0,2}/|src/|tests/|vscode-extension/|\.vscode/)[^\s,;:()]+|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8}",
        goal,
    )
    paths: list[str] = []
    for match in matches:
        candidate = _normalize_path_token(match)
        if not _looks_like_explicit_path(candidate):
            continue
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _pin_research_paths(
    research: dict[str, Any],
    pinned_files: list[str],
) -> dict[str, Any]:
    if not pinned_files:
        return research

    likely_files = list(research.get("likely_files", []))
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in pinned_files:
        merged.append({"path": path, "reason": "explicit path", "score": 10})
        seen.add(path)

    for item in likely_files:
        path = str(item.get("path", "")).strip()
        if not path or path in seen:
            continue
        merged.append(item)
        seen.add(path)

    updated = dict(research)
    updated["likely_files"] = merged
    return updated


def _approved_files_from_run(run: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    pinned_files = [str(item).strip() for item in run.get("pinned_files", []) if str(item).strip()]
    source_items = pinned_files or [str(item.get("path", "")).strip() for item in run.get("likely_files", [])]
    for path in source_items:
        if not path or _is_disallowed_target(path):
            continue
        if path not in paths:
            paths.append(path)
        if len(paths) >= MAX_EDIT_FILES:
            break
    return paths


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


def _recent_penalty(runs: list[dict[str, Any]], category: str) -> float:
    penalty = 0.0
    for run in reversed(runs[-5:]):
        if run.get("candidate", {}).get("category") != category:
            continue
        if run.get("state") in {"rolled_back", "rejected"}:
            penalty += 15.0
    return penalty


def _score_candidate(
    *,
    confidence: float,
    recurrence: int,
    impact: float,
    risk: float,
    penalty: float,
) -> float:
    recurrence_score = min(max(recurrence, 1), 5)
    bounded_risk = min(max(risk, 0.0), 1.0)
    return round((confidence * 40.0) + (recurrence_score * 8.0) + (impact * 30.0) + ((1.0 - bounded_risk) * 20.0) - penalty, 2)


def _build_candidate(
    *,
    category: str,
    goal: str,
    summary: str,
    confidence: float,
    recurrence: int,
    impact: float,
    risk: float,
    evidence: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prior_runs = runs or []
    penalty = _recent_penalty(prior_runs, category)
    return {
        "category": category,
        "goal": goal,
        "summary": summary,
        "confidence": confidence,
        "recurrence": recurrence,
        "impact": impact,
        "risk": risk,
        "evidence": evidence or {},
        "score": _score_candidate(
            confidence=confidence,
            recurrence=recurrence,
            impact=impact,
            risk=risk,
            penalty=penalty,
        ),
        "recent_failure_penalty": penalty,
    }


def _repeated_route_recovery_candidate(
    workspace_root: str,
    runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    prompt_events = read_prompt_events(workspace_root, limit=200)
    traces = read_output_traces(workspace_root, limit=200)
    event_by_id = {str(item.get("id", "")): item for item in prompt_events if item.get("id")}
    recoveries: dict[str, dict[str, Any]] = {}

    for trace in traces:
        tools_used = trace.get("tools_used", [])
        if not isinstance(tools_used, list) or len(tools_used) < 2:
            continue
        event = event_by_id.get(str(trace.get("prompt_event_id", "")))
        if not event:
            continue
        prompt = str(event.get("raw_prompt", "")).strip()
        if not prompt:
            continue
        entry = recoveries.setdefault(prompt, {"count": 0, "tools_used": tools_used})
        entry["count"] += 1

    if not recoveries:
        return None

    prompt, payload = max(recoveries.items(), key=lambda item: item[1]["count"])
    if int(payload["count"]) < 2:
        return None

    return _build_candidate(
        category="route_recovery",
        goal=prompt,
        summary=f"Eliminate repeated reroute for '{prompt}' so it succeeds on the first route.",
        confidence=0.88,
        recurrence=int(payload["count"]),
        impact=0.78,
        risk=0.22,
        evidence={"tools_used": payload["tools_used"]},
        runs=runs,
    )


def _benchmark_failure_candidate(
    workspace_root: str,
    runs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    report = build_status_report(workspace_root, mode="full")
    failed_checks = [
        str(check.get("name", "unknown"))
        for check in report.get("benchmark", {}).get("checks", [])
        if not check.get("passed", False)
    ]
    if not failed_checks:
        return None

    return _build_candidate(
        category="targeted_test_failure",
        goal=f"Fix targeted test failures: {', '.join(failed_checks)}",
        summary=f"Repair failing benchmark/test checks: {', '.join(failed_checks)}.",
        confidence=0.82,
        recurrence=len(failed_checks),
        impact=0.86,
        risk=0.38,
        evidence={"failed_checks": failed_checks},
        runs=runs,
    )


def _low_success_pattern_candidate(engine: "ChatEngine", runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    analysis = engine.self_builder.patterns.get("analysis", {})
    failed_patterns = analysis.get("failed_patterns", [])
    if not failed_patterns:
        return None

    pattern = failed_patterns[0]
    query = str(pattern.get("query", "")).strip() or "improve low-success learned pattern"
    return _build_candidate(
        category="low_success_pattern",
        goal=query,
        summary=f"Improve a low-success learned pattern based on recent failures: {query}",
        confidence=max(0.55, 1.0 - float(analysis.get("success_rate", 0.0))),
        recurrence=len(failed_patterns),
        impact=0.65,
        risk=0.18,
        evidence={"reason": pattern.get("reason", "unknown")},
        runs=runs,
    )


def _select_candidate(
    workspace_root: str,
    engine: "ChatEngine",
    *,
    goal: str = "",
) -> dict[str, Any]:
    runs = _load_runs(workspace_root)
    explicit_goal = goal.strip()
    if explicit_goal:
        return _build_candidate(
            category="explicit_goal",
            goal=explicit_goal,
            summary=f"User-requested improvement: {explicit_goal}",
            confidence=0.98,
            recurrence=1,
            impact=0.95,
            risk=0.32,
            evidence={"source": "user_goal"},
            runs=runs,
        )

    readiness = run_engine_readiness_suite(engine)
    failing = next((item for item in readiness.get("results", []) if not item.get("passed", False)), None)
    if failing:
        prompt = str(failing.get("prompt", "")).strip() or str(failing.get("name", "readiness canary"))
        expected_action = str(failing.get("expected_action", "unknown"))
        return _build_candidate(
            category="readiness_canary",
            goal=prompt,
            summary=f"Fix failing readiness canary '{failing.get('name', prompt)}' so it routes to {expected_action}.",
            confidence=0.92,
            recurrence=max(1, int(readiness.get("failed", 1))),
            impact=0.9,
            risk=0.28,
            evidence={"expected_action": expected_action},
            runs=runs,
        )

    route_candidate = _repeated_route_recovery_candidate(workspace_root, runs)
    if route_candidate:
        return route_candidate

    test_candidate = _benchmark_failure_candidate(workspace_root, runs)
    if test_candidate:
        return test_candidate

    learned_candidate = _low_success_pattern_candidate(engine, runs)
    if learned_candidate:
        return learned_candidate

    return _build_candidate(
        category="status_gap",
        goal="Improve overall readiness and runtime reliability",
        summary="No urgent signal stood out, so improve the highest-value status gap from the current repo state.",
        confidence=0.7,
        recurrence=1,
        impact=0.6,
        risk=0.2,
        evidence={},
        runs=runs,
    )


def _persist_run(workspace_root: str, run: dict[str, Any]) -> dict[str, Any]:
    runs = _load_runs(workspace_root)
    existing = _find_run(runs, str(run.get("run_id", "")))
    run["updated_at"] = _utc_now_iso()
    if existing is None:
        runs.append(run)
    else:
        existing.clear()
        existing.update(run)
    _save_runs(workspace_root, runs)
    return run


def create_self_improvement_plan(
    workspace_root: str,
    engine: "ChatEngine",
    *,
    goal: str = "",
    prefer_web: bool = False,
    source: str = "chat",
) -> dict[str, Any]:
    candidate = _select_candidate(workspace_root, engine, goal=goal)
    pinned_files = _extract_explicit_paths(candidate["goal"])
    research = build_research_payload(engine, candidate["goal"], prefer_web=prefer_web)
    research = _pin_research_paths(research, pinned_files)
    approved_files = _approved_files_from_run(
        {
            "pinned_files": pinned_files,
            "likely_files": research.get("likely_files", []),
        }
    )
    verification = build_verification_plan(approved_files) if approved_files else {
        "descriptions": research.get("verification_plan", []),
        "steps": research.get("verification_plan_steps", []),
    }
    timestamp = _utc_now_iso()
    run = {
        "run_id": f"sir_{uuid4().hex[:10]}",
        "mode": SELF_IMPROVEMENT_MODE,
        "state": "proposed",
        "goal": candidate["goal"],
        "source": source,
        "candidate": candidate,
        "candidate_summary": candidate["summary"],
        "pinned_files": pinned_files,
        "approved_files": approved_files,
        "likely_files": research.get("likely_files", []),
        "verification_plan": verification.get("descriptions", []),
        "verification_plan_steps": verification.get("steps", []),
        "web_research_allowed": bool(research.get("web", {}).get("enabled", False)),
        "web_research_used": bool(research.get("web_research_used", False)),
        "research": research,
        "rollback_performed": False,
        "blocked_reason": None,
        "last_error": None,
        "touched_files": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "events": [],
    }
    _append_event(run, "select", f"Selected candidate: {candidate['category']}")
    _append_event(run, "research", f"Researched goal: {candidate['goal']}")
    if pinned_files:
        _append_event(run, "pin", f"Pinned files: {', '.join(pinned_files)}")
    if approved_files:
        _append_event(run, "approve_scope", f"Approve run with files: {', '.join(approved_files)}")
    _append_event(run, "state", "Proposal created; awaiting approval")
    engine.self_builder.record_run_outcome(
        run_id=run["run_id"],
        state=run["state"],
        goal=run["goal"],
        category=candidate["category"],
        rollback_performed=False,
        verification_passed=False,
    )
    _persist_run(workspace_root, run)
    return run


def _resolve_target(workspace_root: str, relative_path: str) -> Path:
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    target.relative_to(root)
    return target


def _is_disallowed_target(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return True
    if normalized.rsplit("/", 1)[-1] in DEPENDENCY_FILES:
        return True
    parts = {part.lower() for part in normalized.split("/")}
    if parts & DISALLOWED_PATH_MARKERS:
        return True
    return False


def _candidate_target_paths(run: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    source_items = run.get("approved_files") or [item.get("path", "") for item in run.get("likely_files", [])]
    for item in source_items[:MAX_EDIT_FILES]:
        path = str(item).strip()
        if not path or _is_disallowed_target(path):
            continue
        if path not in paths:
            paths.append(path)
    return paths[:MAX_EDIT_FILES]


def _dirty_target_paths(workspace_root: str, paths: list[str]) -> list[str]:
    if not paths:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(workspace_root).resolve()), "status", "--porcelain", "--", *paths],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return []

    dirty: list[str] = []
    for line in result.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        dirty.append(text[3:] if len(text) > 3 else text)
    return dirty


def _rewrite_instruction(run: dict[str, Any], path: str) -> str:
    return (
        "Implement the approved self-improvement proposal for this one file only. "
        "Make the smallest safe change that advances the goal. "
        "Do not rename files, add dependencies, or touch unrelated behavior.\n\n"
        f"Goal: {run.get('goal', '')}\n"
        f"Candidate summary: {run.get('candidate_summary', '')}\n"
        f"Target file: {path}"
    )


def _count_changed_lines(diff: str) -> int:
    changed = 0
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed += 1
    return changed


def _generate_edit_proposals(
    workspace_root: str,
    engine: "ChatEngine",
    run: dict[str, Any],
    target_paths: list[str],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for path in target_paths:
        target = _resolve_target(workspace_root, path)
        if not target.exists():
            continue
        original = target.read_text(encoding="utf-8")
        updated = engine.agent.rewrite_file(path, _rewrite_instruction(run, path), original)
        if updated == original:
            continue
        diff = preview_diff(original, updated, path)
        proposals.append(
            {
                "path": path,
                "original": original,
                "updated": updated,
                "diff": diff,
                "changed_lines": _count_changed_lines(diff),
            }
        )
    return proposals


def _run_verification(
    workspace_root: str,
    engine: "ChatEngine",
    run: dict[str, Any],
) -> dict[str, Any]:
    steps = run.get("verification_plan_steps", [])
    results: list[dict[str, Any]] = []
    for step in steps:
        kind = str(step.get("kind", "command"))
        command = str(step.get("command", ""))
        if kind == "readiness":
            report = run_engine_readiness_suite(engine)
            ok = report.get("status") == "pass"
            results.append(
                {
                    "kind": "readiness",
                    "success": ok,
                    "command": command,
                    "summary": report.get("status", "unknown"),
                }
            )
            if not ok:
                return {
                    "success": False,
                    "failed_step": "readiness",
                    "results": results,
                    "message": "Readiness canaries failed after apply.",
                }
            continue

        result = run_test_command(command, timeout=600, cwd=workspace_root)
        results.append(
            {
                "kind": "command",
                "success": bool(result.get("success", False)),
                "command": command,
                "returncode": result.get("returncode"),
                "stderr": str(result.get("stderr", ""))[:400],
                "stdout": str(result.get("stdout", ""))[:400],
            }
        )
        if not result.get("success", False):
            return {
                "success": False,
                "failed_step": command,
                "results": results,
                "message": f"Verification failed: {command}",
            }

    return {
        "success": True,
        "failed_step": None,
        "results": results,
        "message": "Verification passed.",
    }


def _rollback_applied_edits(workspace_root: str, applied_edits: list[dict[str, Any]]) -> None:
    for item in reversed(applied_edits):
        snapshot = item.get("snapshot")
        path = str(item.get("path", ""))
        if snapshot and path:
            rollback_snapshot(workspace_root, path, snapshot)


def apply_self_improvement_run(
    workspace_root: str,
    engine: "ChatEngine",
    run_id: str,
) -> dict[str, Any]:
    run = get_self_improvement_run(workspace_root, run_id)
    if run is None:
        return {
            "run_id": run_id,
            "mode": SELF_IMPROVEMENT_MODE,
            "state": "rejected",
            "goal": "",
            "candidate_summary": "Self-improvement run not found.",
            "pinned_files": [],
            "approved_files": [],
            "likely_files": [],
            "verification_plan": [],
            "web_research_used": False,
            "events": [{"kind": "error", "message": f"Run {run_id} was not found."}],
            "rollback_performed": False,
            "last_error": f"Run {run_id} was not found.",
        }

    if run.get("state") == "verified":
        _append_event(run, "status", "Run already verified; no further apply needed")
        return _persist_run(workspace_root, run)

    run["state"] = "approved"
    run["blocked_reason"] = None
    _append_event(run, "approve", "Approval recorded; validating bounded apply")

    approved_files = [str(item).strip() for item in run.get("approved_files", []) if str(item).strip()]
    if not approved_files:
        run["blocked_reason"] = "No approved file allowlist is attached to this run."
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    target_paths = _candidate_target_paths(run)
    if not target_paths:
        run["blocked_reason"] = "No safe target files were available for bounded apply."
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    disallowed_targets = [path for path in target_paths if path not in approved_files]
    if disallowed_targets:
        run["blocked_reason"] = f"Apply rejected: targets outside approved allowlist: {', '.join(disallowed_targets)}"
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    dirty = _dirty_target_paths(workspace_root, target_paths)
    if dirty:
        run["blocked_reason"] = f"Dirty target files prevent apply: {', '.join(dirty)}"
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    proposals = _generate_edit_proposals(workspace_root, engine, run, target_paths)
    disallowed_proposals = [
        str(item.get("path", "")).strip()
        for item in proposals
        if str(item.get("path", "")).strip() not in approved_files
    ]
    if disallowed_proposals:
        run["blocked_reason"] = (
            "Apply rejected: generated edits outside approved allowlist: "
            f"{', '.join(disallowed_proposals)}"
        )
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    changed_lines = sum(int(item.get("changed_lines", 0)) for item in proposals)
    if not proposals:
        run["blocked_reason"] = "No bounded file edits were produced for this proposal."
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    if len(proposals) > MAX_EDIT_FILES or changed_lines > MAX_CHANGED_LINES:
        run["blocked_reason"] = (
            f"Bounded apply rejected: {len(proposals)} files and {changed_lines} changed lines "
            f"exceed limits ({MAX_EDIT_FILES} files / {MAX_CHANGED_LINES} lines)."
        )
        run["last_error"] = run["blocked_reason"]
        _append_event(run, "blocked", run["blocked_reason"])
        engine.self_builder.record_run_outcome(
            run_id=run["run_id"],
            state=run["state"],
            goal=run.get("goal", ""),
            category=run.get("candidate", {}).get("category", "unknown"),
            rollback_performed=False,
            verification_passed=False,
        )
        return _persist_run(workspace_root, run)

    applied_edits: list[dict[str, Any]] = []
    for proposal in proposals:
        applied = apply_file_edit(workspace_root, proposal["path"], proposal["updated"])
        applied_edits.append(
            {
                "path": proposal["path"],
                "snapshot": applied.get("snapshot"),
                "diff": proposal["diff"],
                "changed_lines": proposal["changed_lines"],
            }
        )

    run["state"] = "applied"
    run["touched_files"] = [item["path"] for item in applied_edits]
    run["changed_lines"] = changed_lines
    run["applied_edits"] = applied_edits
    _append_event(run, "apply", f"Applied bounded edits to {len(applied_edits)} file(s)")

    verification = _run_verification(workspace_root, engine, run)
    run["verification"] = verification
    if not verification.get("success", False):
        _rollback_applied_edits(workspace_root, applied_edits)
        run["state"] = "rolled_back"
        run["rollback_performed"] = True
        run["last_error"] = str(verification.get("message", "verification failed"))
        _append_event(run, "rollback", run["last_error"])
    else:
        run["state"] = "verified"
        run["rollback_performed"] = False
        run["last_error"] = None
        _append_event(run, "verify", "Verification passed; run accepted")

    engine.self_builder.record_run_outcome(
        run_id=run["run_id"],
        state=run["state"],
        goal=run.get("goal", ""),
        category=run.get("candidate", {}).get("category", "unknown"),
        rollback_performed=bool(run.get("rollback_performed")),
        verification_passed=run["state"] == "verified",
    )
    _persist_run(workspace_root, run)
    return run


def format_self_improvement_run(run: dict[str, Any]) -> str:
    likely_files = run.get("likely_files", [])
    pinned_files = [str(item) for item in run.get("pinned_files", []) if str(item)]
    approved_files = [str(item) for item in run.get("approved_files", []) if str(item)]
    verification = run.get("verification_plan", [])
    lines = [
        "♻️ Self-Improvement Run",
        f"  • Run ID: {run.get('run_id', 'unknown')}",
        f"  • Mode: {run.get('mode', SELF_IMPROVEMENT_MODE)}",
        f"  • State: {run.get('state', 'unknown')}",
        f"  • Goal: {run.get('goal', 'unknown')}",
        f"  • Candidate: {run.get('candidate_summary', 'unknown')}",
        f"  • Web research used: {'yes' if run.get('web_research_used') else 'no'}",
        f"  • Rollback performed: {'yes' if run.get('rollback_performed') else 'no'}",
    ]

    if run.get("blocked_reason"):
        lines.append(f"  • Blocked: {run['blocked_reason']}")
    if run.get("last_error"):
        lines.append(f"  • Last error: {run['last_error']}")
    if pinned_files:
        lines.append(f"  • Pinned files: {', '.join(pinned_files)}")
    if approved_files:
        lines.append(f"  • Approve run with files: {', '.join(approved_files)}")

    lines.append("  • Likely files:")
    if likely_files:
        for item in likely_files:
            if isinstance(item, dict):
                lines.append(f"    - {item.get('path')} ({item.get('reason', 'unknown')})")
            else:
                lines.append(f"    - {item}")
    else:
        lines.append("    - none identified")

    lines.append("  • Verification plan:")
    if verification:
        for item in verification:
            lines.append(f"    - {item}")
    else:
        lines.append("    - none")

    events = run.get("events", [])[-5:]
    if events:
        lines.append("  • Recent events:")
        for event in events:
            lines.append(f"    - [{event.get('kind')}] {event.get('message')}")

    return "\n".join(lines)
