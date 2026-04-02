import json
import os
import sys
from pathlib import Path

from src.agents.coding_agent import CodingAgent
from src.app_service import AppService
from src.tools.approval_policy import check_action_approval
from src.tools.audit_export import export_audit_markdown
from src.tools.autofix import run_autofix_loop
from src.tools.autofix_state import load_autofix_state
from src.tools.benchmark_runner import run_benchmark_suite
from src.tools.budget_tracker import (
    estimate_cost_usd,
    evaluate_budgets,
    load_budget_config,
    read_metrics,
    set_budget_value,
    summarize_costs,
)
from src.tools.chat_engine import run_chat_session
from src.tools.commanding import ActionRequest
from src.tools.compliance_summary import build_compliance_summary
from src.tools.context_packer import pack_context
from src.tools.cost_attribution import summarize_costs_by_trace
from src.tools.dependency_inventory import read_dependency_inventory
from src.tools.decision_timeline import build_decision_timeline
from src.tools.docs_assistant import build_doc_update
from src.tools.eval_runner import run_evaluation_suite
from src.tools.fix_memory import retrieve_similar_fixes
from src.tools.gate_runner import run_regression_gate
from src.tools.incident_automation import build_incident_timeline, generate_incident_report
from src.tools.license_scanner import scan_dependency_licenses
from src.tools.live_mode import (
    SLICE_CATALOG,
    load_live_mode_state,
    run_live_mode,
    save_live_mode_state,
    unlock_slice,
)
from src.tools.logger import load_audit_events
from src.tools.patch_applier import apply_file_edit, preview_diff
from src.tools.patch_guard import validate_unified_diff
from src.tools.playbook_manager import get_playbook_status, scaffold_playbooks
from src.tools.postmortem_builder import generate_postmortem_from_blocker
from src.tools.project_memory import get_notes, remember_note, search_notes
from src.tools.read_policy import ReadFirstPolicy, check_read_first
from src.tools.release_notes import generate_release_notes
from src.tools.repo_index import build_file_index
from src.tools.retention import cleanup_reports
from src.tools.self_improve import run_self_improvement_cycles
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.status_report import export_status_markdown
from src.tools.symbol_index import build_symbol_index
from src.tools.task_planner import build_task_plan
from src.tools.telemetry import summarize_telemetry
from src.tools.tool_policy import recommend_command
from src.ui.terminal_ui import run_terminal_ui

READ_POLICY = ReadFirstPolicy()


def _print_usage():
    print("Usage:")
    print("  python -m src.main \"<coding prompt>\"")
    print("  python -m src.main edit <relative_path> \"<instruction>\" [--yes]")
    print("  python -m src.main capabilities")
    print("  python -m src.main plan \"<request>\"")
    print("  python -m src.main tui")
    print("  python -m src.main chat")
    print("  python -m src.main app-command \"<natural language command>\"")
    print("  python -m src.main autofix <relative_path> \"<instruction>\" [--tests \"<cmd>\"] [--max-attempts N] [--multi] [--no-flaky-confirm]")
    print("  python -m src.main audit <trace_id>")
    print("  python -m src.main memory <target_path> <failure_category>")
    print("  python -m src.main blocker <trace_id>")
    print("  python -m src.main index")
    print("  python -m src.main symbols")
    print("  python -m src.main search <query>")
    print("  python -m src.main context <query> [--chars N]")
    print("  python -m src.main read <relative_path>")
    print("  python -m src.main validate-diff <relative_path>")
    print("  python -m src.main mode <explain|implement|refactor|optimize|secure> <request>")
    print("  python -m src.main debug-guide <issue>")
    print("  python -m src.main notebook-guide <task>")
    print("  python -m src.main task-plan <request>")
    print("  python -m src.main doc-update [changed_files...]")
    print("  python -m src.main project-memory add <key> <value>")
    print("  python -m src.main project-memory get [key]")
    print("  python -m src.main project-memory search <query>")
    print("  python -m src.main policy-recommend <task_type> <default_command>")
    print("  python -m src.main policy-check <action> [--role ROLE] [--auto]")
    print("  python -m src.main gate [test_command]")
    print("  python -m src.main telemetry")
    print("  python -m src.main decision-timeline [--limit N]")
    print("  python -m src.main release-notes <version>")
    print("  python -m src.main audit-export <trace_id>")
    print("  python -m src.main retention-clean [--days N]")
    print("  python -m src.main deps")
    print("  python -m src.main license-scan")
    print("  python -m src.main playbooks scaffold|status")
    print("  python -m src.main compliance")
    print("  python -m src.main budget show|set|check|metrics ...")
    print("  python -m src.main cost-estimate <input_tokens> <output_tokens>")
    print("  python -m src.main cost-summary")
    print("  python -m src.main cost-by-trace")
    print("  python -m src.main incident-timeline <trace_id>")
    print("  python -m src.main incident-report <trace_id>")
    print("  python -m src.main postmortem <trace_id>")
    print("  python -m src.main benchmark [--profile default|strict]")
    print("  python -m src.main status [--full]")
    print("  python -m src.main status-export [--full]")
    print("  python -m src.main self-improve [--cycles N] [--target-score X]")
    print("  python -m src.main live [--interval N] [--iterations N] [--allow-unlocked]")
    print("  python -m src.main live status")
    print("  python -m src.main live unlock <slice>")
    print("  python -m src.main live reset")
    print("  python -m src.main resume-autofix <trace_id>")
    print("  python -m src.main eval")

def main():
    agent = CodingAgent()

    args = sys.argv[1:]
    if args and args[0] == "capabilities":
        print(agent.capabilities)
        return

    if args and args[0] == "plan":
        request = " ".join(args[1:]).strip()
        if not request:
            print("No planning request provided.")
            return
        action = agent.plan_action(request)
        print(action)
        return

    if args and args[0] == "tui":
        run_terminal_ui(agent)
        return

    if args and args[0] == "chat":
        run_chat_session(str(Path.cwd()))
        return

    if args and args[0] == "app-command":
        command = " ".join(args[1:]).strip()
        if not command:
            print("Usage: python -m src.main app-command \"<natural language command>\"")
            return
        service = AppService(str(Path.cwd()))
        print(service.run_command(command, source="cli"))
        return

    if args and args[0] == "audit":
        if len(args) < 2:
            print("Usage: python -m src.main audit <trace_id>")
            return
        trace_id = args[1]
        events = load_audit_events(str(Path.cwd()), trace_id)
        if not events:
            print("No audit events found for trace.")
            return
        for event in events:
            print(event)
        return

    if args and args[0] == "memory":
        if len(args) < 3:
            print("Usage: python -m src.main memory <target_path> <failure_category>")
            return
        rows = retrieve_similar_fixes(str(Path.cwd()), args[1], args[2], limit=5)
        print(rows)
        return

    if args and args[0] == "blocker":
        if len(args) < 2:
            print("Usage: python -m src.main blocker <trace_id>")
            return
        path = Path.cwd() / ".autofix_reports" / f"{args[1]}.json"
        if not path.exists():
            print("Blocker report not found.")
            return
        print(json.loads(path.read_text(encoding="utf-8")))
        return

    if args and args[0] == "index":
        print(build_file_index(str(Path.cwd())))
        return

    if args and args[0] == "symbols":
        print(build_symbol_index(str(Path.cwd())))
        return

    if args and args[0] == "search":
        if len(args) < 2:
            print("Usage: python -m src.main search <query>")
            return
        query = " ".join(args[1:]).strip()
        service = AppService(str(Path.cwd()))
        result = service.run_request(
            ActionRequest(
                action="search",
                confidence=1.0,
                raw_input=f"search {query}",
                params={"query": query},
            ),
            source="cli",
        )
        print(result["response"])
        return

    if args and args[0] == "context":
        if len(args) < 2:
            print("Usage: python -m src.main context <query> [--chars N]")
            return
        clean = args[1:]
        max_chars = 4000
        if "--chars" in clean:
            idx = clean.index("--chars")
            if idx + 1 < len(clean):
                max_chars = int(clean[idx + 1])
                del clean[idx:idx + 2]
        snippets = retrieve_relevant_snippets(str(Path.cwd()), " ".join(clean), limit=8)
        print(pack_context(snippets, max_chars=max_chars))
        return

    if args and args[0] == "read":
        if len(args) != 2:
            print("Usage: python -m src.main read <relative_path>")
            return
        relative_path = args[1]
        path = Path.cwd() / relative_path
        if not path.exists():
            print("Path not found")
            return
        READ_POLICY.record_read(relative_path)
        print(path.read_text(encoding="utf-8"))
        return

    if args and args[0] == "validate-diff":
        if len(args) != 2:
            print("Usage: python -m src.main validate-diff <relative_path>")
            return
        relative_path = args[1]
        check_read_first(READ_POLICY, relative_path)
        path = Path.cwd() / relative_path
        content = path.read_text(encoding="utf-8")
        diff = preview_diff(content, content, relative_path)
        print(validate_unified_diff(diff))
        return

    if args and args[0] == "mode":
        if len(args) < 3:
            print("Usage: python -m src.main mode <explain|implement|refactor|optimize|secure> <request>")
            return
        mode = args[1]
        request = " ".join(args[2:]).strip()
        print(agent.run_mode(mode, request))
        return

    if args and args[0] == "debug-guide":
        if len(args) < 2:
            print("Usage: python -m src.main debug-guide <issue>")
            return
        issue = " ".join(args[1:]).strip()
        print(
            agent.run_mode(
                "debug",
                f"Provide breakpoint strategy, stack inspection steps, and likely root causes for: {issue}",
            )
        )
        return

    if args and args[0] == "notebook-guide":
        if len(args) < 2:
            print("Usage: python -m src.main notebook-guide <task>")
            return
        task = " ".join(args[1:]).strip()
        print(
            agent.run_mode(
                "notebook",
                f"Provide cell-by-cell plan with run/fix loop for: {task}",
            )
        )
        return

    if args and args[0] == "task-plan":
        request = " ".join(args[1:]).strip()
        if not request:
            print("Usage: python -m src.main task-plan <request>")
            return
        print(build_task_plan(request))
        return

    if args and args[0] == "doc-update":
        changed_files = args[1:] if len(args) > 1 else None
        print(build_doc_update(str(Path.cwd()), changed_files=changed_files))
        return

    if args and args[0] == "project-memory":
        if len(args) < 2:
            print("Usage: python -m src.main project-memory <add|get|search> ...")
            return
        sub = args[1]
        if sub == "add":
            if len(args) < 4:
                print("Usage: python -m src.main project-memory add <key> <value>")
                return
            key = args[2]
            value = " ".join(args[3:]).strip()
            print(remember_note(str(Path.cwd()), key=key, value=value))
            return
        if sub == "get":
            key = args[2] if len(args) > 2 else None
            print(get_notes(str(Path.cwd()), key=key, limit=20))
            return
        if sub == "search":
            if len(args) < 3:
                print("Usage: python -m src.main project-memory search <query>")
                return
            print(search_notes(str(Path.cwd()), query=" ".join(args[2:]), limit=10))
            return
        print("Usage: python -m src.main project-memory <add|get|search> ...")
        return

    if args and args[0] == "policy-recommend":
        if len(args) < 3:
            print("Usage: python -m src.main policy-recommend <task_type> <default_command>")
            return
        task_type = args[1]
        default_command = " ".join(args[2:]).strip()
        print(recommend_command(str(Path.cwd()), task_type, default_command))
        return

    if args and args[0] == "policy-check":
        if len(args) < 2:
            print("Usage: python -m src.main policy-check <action> [--role ROLE] [--auto]")
            return
        action = args[1]
        role = os.getenv("APP_ROLE", "developer")
        auto = "--auto" in args
        if "--role" in args:
            idx = args.index("--role")
            if idx + 1 < len(args):
                role = args[idx + 1]
        print(check_action_approval(action=action, role=role, auto_apply_requested=auto))
        return

    if args and args[0] == "gate":
        profile = "standard"
        clean = args[1:]
        if "--profile" in clean:
            idx = clean.index("--profile")
            if idx + 1 < len(clean):
                profile = clean[idx + 1]
                del clean[idx:idx + 2]
        command = " ".join(clean).strip() if clean else "python -m pytest -q"
        print(run_regression_gate(command, workspace_root=str(Path.cwd()), profile=profile))
        return

    if args and args[0] == "telemetry":
        print(summarize_telemetry(str(Path.cwd())))
        return

    if args and args[0] == "decision-timeline":
        limit = 200
        if "--limit" in args:
            idx = args.index("--limit")
            if idx + 1 < len(args):
                limit = int(args[idx + 1])
        print(build_decision_timeline(str(Path.cwd()), limit=limit))
        return

    if args and args[0] == "release-notes":
        if len(args) != 2:
            print("Usage: python -m src.main release-notes <version>")
            return
        print(generate_release_notes(str(Path.cwd()), version=args[1]))
        return

    if args and args[0] == "audit-export":
        if len(args) != 2:
            print("Usage: python -m src.main audit-export <trace_id>")
            return
        print(export_audit_markdown(str(Path.cwd()), args[1]))
        return

    if args and args[0] == "retention-clean":
        days = 14
        if "--days" in args:
            idx = args.index("--days")
            if idx + 1 < len(args):
                days = int(args[idx + 1])
        print(cleanup_reports(str(Path.cwd()), older_than_days=days))
        return

    if args and args[0] == "deps":
        print(read_dependency_inventory(str(Path.cwd())))
        return

    if args and args[0] == "license-scan":
        print(scan_dependency_licenses(str(Path.cwd())))
        return

    if args and args[0] == "playbooks":
        if len(args) < 2:
            print("Usage: python -m src.main playbooks scaffold|status")
            return
        if args[1] == "scaffold":
            print(scaffold_playbooks(str(Path.cwd())))
            return
        if args[1] == "status":
            print(get_playbook_status(str(Path.cwd())))
            return
        print("Usage: python -m src.main playbooks scaffold|status")
        return

    if args and args[0] == "compliance":
        print(build_compliance_summary(str(Path.cwd())))
        return

    if args and args[0] == "budget":
        if len(args) < 2:
            print("Usage: python -m src.main budget show|set|check|metrics ...")
            return
        sub = args[1]
        if sub == "show":
            print(load_budget_config(str(Path.cwd())))
            return
        if sub == "set":
            if len(args) != 4:
                print("Usage: python -m src.main budget set <key> <value>")
                return
            key = args[2]
            value = float(args[3])
            print(set_budget_value(str(Path.cwd()), key, value))
            return
        if sub == "check":
            print(evaluate_budgets(str(Path.cwd())))
            return
        if sub == "metrics":
            limit = int(args[2]) if len(args) > 2 else 20
            print(read_metrics(str(Path.cwd()), limit=limit))
            return
        print("Usage: python -m src.main budget show|set|check|metrics ...")
        return

    if args and args[0] == "cost-estimate":
        if len(args) != 3:
            print("Usage: python -m src.main cost-estimate <input_tokens> <output_tokens>")
            return
        input_tokens = int(args[1])
        output_tokens = int(args[2])
        print(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimate_cost_usd(
                    str(Path.cwd()),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                ),
            }
        )
        return

    if args and args[0] == "cost-summary":
        print(summarize_costs(str(Path.cwd())))
        return

    if args and args[0] == "cost-by-trace":
        print(summarize_costs_by_trace(str(Path.cwd())))
        return

    if args and args[0] == "incident-timeline":
        if len(args) != 2:
            print("Usage: python -m src.main incident-timeline <trace_id>")
            return
        print(build_incident_timeline(str(Path.cwd()), args[1]))
        return

    if args and args[0] == "incident-report":
        if len(args) != 2:
            print("Usage: python -m src.main incident-report <trace_id>")
            return
        print(generate_incident_report(str(Path.cwd()), args[1]))
        return

    if args and args[0] == "postmortem":
        if len(args) != 2:
            print("Usage: python -m src.main postmortem <trace_id>")
            return
        print(generate_postmortem_from_blocker(str(Path.cwd()), args[1]))
        return

    if args and args[0] == "benchmark":
        profile = "default"
        if "--profile" in args:
            idx = args.index("--profile")
            if idx + 1 < len(args):
                profile = args[idx + 1]
        print(run_benchmark_suite(str(Path.cwd()), profile=profile))
        return

    if args and args[0] == "status":
        mode = "full" if "--full" in args else "lightweight"
        service = AppService(str(Path.cwd()))
        result = service.run_request(
            ActionRequest(
                action="status",
                confidence=1.0,
                raw_input="status --full" if mode == "full" else "status",
                params={"validation_mode": mode},
            ),
            source="cli",
        )
        print(result["response"])
        return

    if args and args[0] == "status-export":
        mode = "full" if "--full" in args else "lightweight"
        print(export_status_markdown(str(Path.cwd()), mode=mode))
        return

    if args and args[0] == "self-improve":
        if any(flag in args for flag in ("--cycles", "--target-score")):
            cycles = 1
            target_score = 95.0
            if "--cycles" in args:
                idx = args.index("--cycles")
                if idx + 1 < len(args):
                    cycles = int(args[idx + 1])
            if "--target-score" in args:
                idx = args.index("--target-score")
                if idx + 1 < len(args):
                    target_score = float(args[idx + 1])

            print(run_self_improvement_cycles(str(Path.cwd()), cycles=cycles, target_score=target_score))
            return

        service = AppService(str(Path.cwd()))
        if len(args) == 1:
            command = "self-improve status"
        elif args[1] == "status":
            command = "self-improve status" if len(args) == 2 else f"self-improve status {' '.join(args[2:])}"
        elif args[1] in {"plan", "run"}:
            command = f"self-improve {args[1]} {' '.join(args[2:]).strip()}".strip()
        elif args[1] in {"apply", "approve"}:
            if len(args) < 3:
                print("Usage: python -m src.main self-improve apply <run_id>")
                return
            command = f"approve self-improve {args[2]}"
        else:
            command = " ".join(args)

        result = service.run_command(command, source="cli")
        print(result["response"])
        return

    if args and args[0] == "live":
        if len(args) >= 2 and args[1] == "status":
            state = load_live_mode_state(str(Path.cwd()))
            print(
                {
                    "state": state,
                    "slice_catalog": SLICE_CATALOG,
                }
            )
            return

        if len(args) >= 2 and args[1] == "unlock":
            if len(args) < 3:
                print("Usage: python -m src.main live unlock <slice>")
                return
            print(unlock_slice(str(Path.cwd()), args[2].strip()))
            return

        if len(args) >= 2 and args[1] == "reset":
            baseline = {
                "enabled": False,
                "mode": "learning_only",
                "points": 0,
                "cycles": 0,
                "unlocked_slices": ["learn"],
                "last_cycle_at": None,
                "last_cycle_summary": {},
            }
            print(save_live_mode_state(str(Path.cwd()), baseline))
            return

        interval = 30
        iterations = 0
        allow_unlocked_slices = "--allow-unlocked" in args

        clean_args = [arg for arg in args[1:] if arg != "--allow-unlocked"]

        if "--interval" in clean_args:
            idx = clean_args.index("--interval")
            if idx + 1 >= len(clean_args):
                print("Usage: python -m src.main live [--interval N] [--iterations N] [--allow-unlocked]")
                return
            interval = int(clean_args[idx + 1])

        if "--iterations" in clean_args:
            idx = clean_args.index("--iterations")
            if idx + 1 >= len(clean_args):
                print("Usage: python -m src.main live [--interval N] [--iterations N] [--allow-unlocked]")
                return
            iterations = int(clean_args[idx + 1])

        print(
            run_live_mode(
                str(Path.cwd()),
                interval_seconds=interval,
                iterations=iterations,
                allow_unlocked_slices=allow_unlocked_slices,
            )
        )
        return

    if args and args[0] == "resume-autofix":
        if len(args) != 2:
            print("Usage: python -m src.main resume-autofix <trace_id>")
            return
        state = load_autofix_state(str(Path.cwd()), args[1])
        if not state:
            print("Autofix state not found.")
            return
        if state.get("status") == "completed":
            print({"message": "Trace already completed", "trace_id": args[1]})
            return
        attempts_so_far = len(state.get("attempts", []))
        max_attempts = max(1, int(state.get("max_attempts", 3)) - attempts_so_far)
        result = run_autofix_loop(
            agent=agent,
            workspace_root=str(Path.cwd()),
            target_path=state["target_path"],
            instruction=f"{state['instruction']}\n\nResume from trace {args[1]}",
            test_command=state.get("test_command"),
            max_attempts=max_attempts,
        )
        print(result)
        return

    if args and args[0] == "eval":
        print(run_evaluation_suite())
        return

    if args and args[0] == "autofix":
        if len(args) < 3:
            _print_usage()
            return

        clean_args = args[1:]
        test_command = None
        max_attempts = 3
        allow_multifile = "--multi" in clean_args
        confirm_flaky = "--no-flaky-confirm" not in clean_args

        clean_args = [arg for arg in clean_args if arg not in {"--multi", "--no-flaky-confirm"}]

        if "--tests" in clean_args:
            idx = clean_args.index("--tests")
            if idx + 1 >= len(clean_args):
                print("Missing value for --tests")
                return
            test_command = clean_args[idx + 1]
            del clean_args[idx:idx + 2]

        if "--max-attempts" in clean_args:
            idx = clean_args.index("--max-attempts")
            if idx + 1 >= len(clean_args):
                print("Missing value for --max-attempts")
                return
            max_attempts = int(clean_args[idx + 1])
            del clean_args[idx:idx + 2]

        target_path = clean_args[0]
        instruction = " ".join(clean_args[1:]).strip()
        if not instruction:
            print("No autofix instruction provided.")
            return

        result = run_autofix_loop(
            agent=agent,
            workspace_root=str(Path.cwd()),
            target_path=target_path,
            instruction=instruction,
            test_command=test_command,
            max_attempts=max_attempts,
            allow_multifile=allow_multifile,
            confirm_flaky=confirm_flaky,
        )

        print(f"Autofix success: {result['success']}")
        print(f"Reason: {result['reason']}")
        print(f"Trace ID: {result['trace_id']}")
        print(f"Audit log: {result['audit_log']}")
        print(f"Test command: {result['test_command']}")
        print(f"Attempts: {len(result['attempts'])}")
        for attempt in result["attempts"]:
            print(f"- Attempt {attempt['attempt']}: test_success={attempt['test_success']}")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        print(f"Planned files: {result.get('planned_files', [])}")
        if result["rolled_back"]:
            print("Changes rolled back to original file.")
        if result["minimal_repro"]:
            print(f"Minimal repro: {result['minimal_repro']}")
        if result["blocker_report"]:
            print(f"Blocker report: {result['blocker_report']['path']}")
        return

    if args and args[0] == "edit":
        if len(args) < 3:
            _print_usage()
            return

        auto_apply = "--yes" in args
        role = os.getenv("APP_ROLE", "developer")
        approval = check_action_approval("edit", role=role, auto_apply_requested=auto_apply)
        if auto_apply and not approval["allowed"]:
            print(f"Auto-apply blocked by policy: {approval['reason']}")
            auto_apply = False
        clean_args = [arg for arg in args[1:] if arg != "--yes"]
        target_path = clean_args[0]
        instruction = " ".join(clean_args[1:]).strip()
        if not instruction:
            print("No edit instruction provided.")
            return

        workspace_root = Path.cwd()
        absolute_target = (workspace_root / target_path).resolve()
        if not absolute_target.exists():
            print(f"Target file does not exist: {target_path}")
            return

        current_content = absolute_target.read_text(encoding="utf-8")
        updated_content = agent.rewrite_file(target_path, instruction, current_content)
        diff = preview_diff(current_content, updated_content, target_path)

        if not diff:
            print("No changes generated.")
            return

        print("\nPatch Preview:\n")
        print(diff)

        should_apply = auto_apply
        if not auto_apply:
            answer = input("Apply these changes? [y/N]: ").strip().lower()
            should_apply = answer == "y"

        if not should_apply:
            print("Edit cancelled.")
            return

        result = apply_file_edit(str(workspace_root), target_path, updated_content)
        print(f"Changes applied to {result['path']}")
        return

    prompt = " ".join(args).strip()
    if not prompt:
        prompt = input("Enter a coding prompt: ").strip()

    if not prompt:
        _print_usage()
        return

    service = AppService(str(Path.cwd()))
    result = service.run_command(prompt, source="cli")
    print(result["response"])

if __name__ == "__main__":
    main()
