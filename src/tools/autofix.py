from pathlib import Path
import json

from src.tools.circuit_breaker import should_trip_circuit_breaker
from src.tools.confidence import score_attempt_confidence
from src.tools.failure_parser import classify_failure
from src.tools.fix_memory import retrieve_similar_fixes, store_fix_memory
from src.tools.logger import get_audit_log_path, log_event, new_trace_id
from src.tools.minimal_repro import write_minimal_repro
from src.tools.multifile_editor import apply_multifile_rewrites
from src.tools.patch_applier import apply_file_edit, preview_diff
from src.tools.project_memory import remember_note
from src.tools.prompt_optimizer import choose_prompt_strategy, record_prompt_outcome
from src.tools.repair_planner import plan_repair_files
from src.tools.repair_strategy import choose_repair_strategy
from src.tools.test_selector import select_test_command
from src.tools.test_runner import run_test_command
from src.tools.tool_policy import recommend_command, record_tool_outcome


def _resolve_target(workspace_root: str, relative_path: str):
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Target path must stay inside workspace root.")
    return target


def run_autofix_loop(
    agent,
    workspace_root: str,
    target_path: str,
    instruction: str,
    test_command: str | None = None,
    max_attempts: int = 3,
    circuit_breaker_repeats: int = 2,
    allow_multifile: bool = False,
    confirm_flaky: bool = True,
):
    trace_id = new_trace_id()
    target = _resolve_target(workspace_root, target_path)
    selected_test_command = test_command or select_test_command(workspace_root, target_path)
    selected_test_command = recommend_command(workspace_root, "autofix", selected_test_command)
    prompt_strategy = choose_prompt_strategy(
        workspace_root,
        options=["concise", "verbose"],
        default="concise",
    )
    audit_log_path = get_audit_log_path(workspace_root, trace_id)
    log_event(
        "autofix_start",
        trace_id,
        workspace_root=workspace_root,
        target_path=target_path,
        test_command=selected_test_command,
        max_attempts=max_attempts,
        circuit_breaker_repeats=circuit_breaker_repeats,
        allow_multifile=allow_multifile,
        confirm_flaky=confirm_flaky,
    )

    if not target.exists():
        return {
            "success": False,
            "reason": f"Target file does not exist: {target_path}",
            "attempts": [],
            "rolled_back": False,
            "trace_id": trace_id,
            "audit_log": audit_log_path,
            "test_command": selected_test_command,
            "blocker_report": None,
            "minimal_repro": None,
        }

    original_content = target.read_text(encoding="utf-8")
    preflight_fixes = retrieve_similar_fixes(workspace_root, target_path, "unknown", limit=3)
    preflight_hints = "\n".join(
        [
            f"- previous strategy={item.get('strategy')} summary={item.get('summary')} success={item.get('success')}"
            for item in preflight_fixes
        ]
    )
    loop_instruction = (
        f"{instruction}\n\n"
        f"Preflight similar-fix hints:\n{preflight_hints or 'none'}"
    )
    attempts = []
    stop_reason = ""
    planned_files = [target_path]

    for attempt_index in range(1, max_attempts + 1):
        current_content = target.read_text(encoding="utf-8")
        updated_content = agent.rewrite_file(target_path, loop_instruction, current_content)
        diff = preview_diff(current_content, updated_content, target_path)

        if not diff:
            attempts.append(
                {
                    "attempt": attempt_index,
                    "applied": False,
                    "test_success": False,
                    "diff": "",
                    "test_result": None,
                    "reason": "No changes generated",
                }
            )
            break

        apply_file_edit(workspace_root, target_path, updated_content)
        if allow_multifile and len(planned_files) > 1:
            apply_multifile_rewrites(
                agent=agent,
                workspace_root=workspace_root,
                target_files=[path for path in planned_files if path != target_path],
                instruction=f"Related-file adjustment for goal: {instruction}",
            )

        command_for_attempt = selected_test_command
        test_result = run_test_command(command_for_attempt)
        failure = classify_failure(
            stdout=test_result["stdout"],
            stderr=test_result["stderr"],
            timed_out=test_result["timed_out"],
        )
        if failure.get("pytest_nodeids"):
            focused = " ".join(failure["pytest_nodeids"][:3])
            command_for_attempt = f"python -m pytest -q {focused}"

        if confirm_flaky and failure["category"] == "flaky":
            confirm_result = run_test_command(selected_test_command)
            if confirm_result["success"]:
                test_result = confirm_result
                failure = classify_failure(
                    stdout=confirm_result["stdout"],
                    stderr=confirm_result["stderr"],
                    timed_out=confirm_result["timed_out"],
                )
                failure["summary"] = "Flaky failure resolved on confirm rerun"

        similar_fixes = retrieve_similar_fixes(
            workspace_root,
            target_path,
            failure["category"],
            limit=3,
        )
        planned_files = plan_repair_files(workspace_root, target_path, failure)
        log_event(
            "autofix_attempt",
            trace_id,
            workspace_root=workspace_root,
            attempt=attempt_index,
            test_success=test_result["success"],
            failure_category=failure["category"],
            planned_files=planned_files,
            similar_fix_count=len(similar_fixes),
        )

        strategy = choose_repair_strategy(failure["category"])
        confidence = score_attempt_confidence(
            failure_category=failure["category"],
            similar_fix_count=len(similar_fixes),
            test_success=test_result["success"],
            flaky_suspected=failure.get("flaky", {}).get("suspected", False),
        )

        attempts.append(
            {
                "attempt": attempt_index,
                "applied": True,
                "test_success": test_result["success"],
                "diff": diff,
                "test_result": test_result,
                "failure": failure,
                "strategy": strategy,
                "planned_files": planned_files,
                "confidence": confidence,
                "test_command_used": command_for_attempt,
                "reason": "",
            }
        )

        if test_result["success"]:
            record_tool_outcome(workspace_root, "autofix", selected_test_command, True)
            record_prompt_outcome(workspace_root, prompt_strategy, True)
            remember_note(
                workspace_root,
                key="autofix_success",
                value=f"target={target_path} strategy={prompt_strategy} trace={trace_id}",
            )
            store_fix_memory(
                workspace_root,
                {
                    "trace_id": trace_id,
                    "target_path": target_path,
                    "failure_category": failure["category"],
                    "strategy": strategy["strategy"],
                    "success": True,
                    "summary": failure.get("summary", ""),
                    "confidence": confidence,
                },
            )
            return {
                "success": True,
                "reason": "Tests passed",
                "attempts": attempts,
                "rolled_back": False,
                "trace_id": trace_id,
                "audit_log": audit_log_path,
                "test_command": selected_test_command,
                "blocker_report": None,
                "minimal_repro": None,
                "planned_files": planned_files,
                "confidence": confidence,
            }

        should_stop, reason = should_trip_circuit_breaker(attempts, min_repeats=circuit_breaker_repeats)
        if should_stop:
            stop_reason = f"Circuit breaker: {reason}"
            log_event("autofix_circuit_breaker", trace_id, workspace_root=workspace_root, reason=reason)
            break

        memory_hints = "\n".join(
            [
                f"- similar_fix strategy={item.get('strategy')} summary={item.get('summary')} success={item.get('success')}"
                for item in similar_fixes
            ]
        )

        loop_instruction = (
            f"{instruction}\n\n"
            f"Repair attempt {attempt_index} failed.\n"
            f"Prompt strategy: {prompt_strategy}\n"
            f"Test command: {selected_test_command}\n"
            f"Failure category: {failure['category']}\n"
            f"Failure summary: {failure['summary']}\n"
            f"Repair hint: {failure['hint']}\n"
            f"Repair strategy: {strategy['strategy']}\n"
            f"Strategy instructions: {strategy['instructions']}\n"
            f"Confidence score: {confidence}\n"
            f"Test command used: {command_for_attempt}\n"
            f"Planned related files (for awareness): {', '.join(planned_files)}\n"
            f"Fix memory hints:\n{memory_hints or 'none'}\n"
            "Fix only this target file to satisfy failing checks.\n"
            "Keep the original goal intact and return only updated file content.\n\n"
            f"STDOUT:\n{test_result['stdout']}\n\n"
            f"STDERR:\n{test_result['stderr']}"
        )

    apply_file_edit(workspace_root, target_path, original_content)
    record_tool_outcome(workspace_root, "autofix", selected_test_command, False)
    record_prompt_outcome(workspace_root, prompt_strategy, False)
    remember_note(
        workspace_root,
        key="autofix_failure",
        value=f"target={target_path} strategy={prompt_strategy} trace={trace_id}",
    )
    last_failure = _get_last_failure(attempts)
    repro_path = write_minimal_repro(
        workspace_root=workspace_root,
        trace_id=trace_id,
        target_path=target_path,
        instruction=instruction,
        test_command=selected_test_command,
        last_failure=last_failure,
    )
    blocker_report = _build_blocker_report(
        trace_id=trace_id,
        target_path=target_path,
        instruction=instruction,
        test_command=selected_test_command,
        attempts=attempts,
        stop_reason=stop_reason or "max_attempts_reached",
    )
    report_path = _write_blocker_report(workspace_root, trace_id, blocker_report)
    log_event("autofix_blocked", trace_id, workspace_root=workspace_root, report_path=report_path, repro_path=repro_path)
    store_fix_memory(
        workspace_root,
        {
            "trace_id": trace_id,
            "target_path": target_path,
            "failure_category": last_failure.get("category", "unknown"),
            "strategy": attempts[-1].get("strategy", {}).get("strategy", "none") if attempts else "none",
            "success": False,
            "summary": last_failure.get("summary", ""),
            "confidence": _get_last_confidence(attempts),
        },
    )
    return {
        "success": False,
        "reason": stop_reason or "Failed to reach passing tests within max attempts",
        "attempts": attempts,
        "rolled_back": True,
        "trace_id": trace_id,
        "audit_log": audit_log_path,
        "test_command": selected_test_command,
        "blocker_report": {
            "path": report_path,
            "summary": blocker_report,
        },
        "minimal_repro": repro_path,
        "planned_files": planned_files,
        "confidence": _get_last_confidence(attempts),
    }


def _build_blocker_report(trace_id: str, target_path: str, instruction: str, test_command: str, attempts: list[dict], stop_reason: str):
    last_failure = _get_last_failure(attempts)
    categories = [attempt.get("failure", {}).get("category", "unknown") for attempt in attempts if attempt.get("failure")]
    return {
        "trace_id": trace_id,
        "target_path": target_path,
        "instruction": instruction,
        "test_command": test_command,
        "attempt_count": len(attempts),
        "stop_reason": stop_reason,
        "failure_categories": categories,
        "last_failure": last_failure,
        "next_steps": [
            "Review blocker report and inspect failing output.",
            "Narrow test scope or patch additional files if needed.",
            "Re-run autofix with stronger instruction context.",
        ],
    }


def _write_blocker_report(workspace_root: str, trace_id: str, report: dict):
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{trace_id}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out_path)


def _get_last_failure(attempts: list[dict]) -> dict:
    for attempt in reversed(attempts):
        failure = attempt.get("failure")
        if failure:
            return failure
    return {}


def _get_last_confidence(attempts: list[dict]) -> float:
    for attempt in reversed(attempts):
        if "confidence" in attempt:
            return attempt["confidence"]
    return 0.0
