import shlex
import json
from pathlib import Path

from src.tools.autofix import run_autofix_loop
from src.tools.fix_memory import retrieve_similar_fixes
from src.tools.logger import load_audit_events
from src.tools.patch_applier import apply_file_edit, preview_diff


def parse_tui_command(raw_line: str):
    parts = shlex.split(raw_line)
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _print_help():
    print("Commands:")
    print("  help")
    print("  capabilities")
    print("  plan <request>")
    print("  generate <prompt>")
    print("  edit <relative_path> <instruction>")
    print("  autofix <relative_path> <instruction> [--multi] [--no-flaky-confirm]")
    print("  audit <trace_id>")
    print("  memory <target_path> <failure_category>")
    print("  blocker <trace_id>")
    print("  quit")


def _handle_edit(agent, workspace_root: Path, target_path: str, instruction: str):
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

    answer = input("Apply these changes? [y/N]: ").strip().lower()
    if answer != "y":
        print("Edit cancelled.")
        return

    result = apply_file_edit(str(workspace_root), target_path, updated_content)
    print(f"Changes applied to {result['path']}")


def run_terminal_ui(agent):
    workspace_root = Path.cwd()
    print("Terminal Copilot Mode (MVP). Type 'help' for commands.")

    while True:
        raw = input("copilot> ").strip()
        command, args = parse_tui_command(raw)

        if not command:
            continue

        if command in {"quit", "exit"}:
            print("Bye.")
            break

        if command == "help":
            _print_help()
            continue

        if command == "capabilities":
            print(agent.capabilities)
            continue

        if command == "plan":
            if not args:
                print("Usage: plan <request>")
                continue
            request = " ".join(args).strip()
            print(agent.plan_action(request))
            continue

        if command == "generate":
            if not args:
                print("Usage: generate <prompt>")
                continue
            prompt = " ".join(args).strip()
            generated_code = agent.generate_code(prompt)
            print("\nGenerated Code:\n")
            print(generated_code)
            print("\nEvaluation Result:\n")
            print(agent.evaluate_code(generated_code))
            continue

        if command == "edit":
            if len(args) < 2:
                print("Usage: edit <relative_path> <instruction>")
                continue
            target_path = args[0]
            instruction = " ".join(args[1:]).strip()
            _handle_edit(agent, workspace_root, target_path, instruction)
            continue

        if command == "autofix":
            if len(args) < 2:
                print("Usage: autofix <relative_path> <instruction>")
                continue
            allow_multifile = "--multi" in args
            confirm_flaky = "--no-flaky-confirm" not in args
            clean_args = [arg for arg in args if arg not in {"--multi", "--no-flaky-confirm"}]
            target_path = clean_args[0]
            instruction = " ".join(clean_args[1:]).strip()
            result = run_autofix_loop(
                agent=agent,
                workspace_root=str(workspace_root),
                target_path=target_path,
                instruction=instruction,
                allow_multifile=allow_multifile,
                confirm_flaky=confirm_flaky,
            )
            print(f"Autofix success: {result['success']}")
            print(f"Reason: {result['reason']}")
            print(f"Trace ID: {result['trace_id']}")
            print(f"Audit log: {result['audit_log']}")
            print(f"Test command: {result['test_command']}")
            print(f"Attempts: {len(result['attempts'])}")
            print(f"Confidence: {result.get('confidence', 0.0)}")
            print(f"Planned files: {result.get('planned_files', [])}")
            if result["minimal_repro"]:
                print(f"Minimal repro: {result['minimal_repro']}")
            if result["blocker_report"]:
                print(f"Blocker report: {result['blocker_report']['path']}")
            continue

        if command == "audit":
            if len(args) != 1:
                print("Usage: audit <trace_id>")
                continue
            events = load_audit_events(str(workspace_root), args[0])
            if not events:
                print("No audit events found for trace.")
                continue
            for event in events:
                print(event)
            continue

        if command == "memory":
            if len(args) != 2:
                print("Usage: memory <target_path> <failure_category>")
                continue
            print(retrieve_similar_fixes(str(workspace_root), args[0], args[1], limit=5))
            continue

        if command == "blocker":
            if len(args) != 1:
                print("Usage: blocker <trace_id>")
                continue
            path = workspace_root / ".autofix_reports" / f"{args[0]}.json"
            if not path.exists():
                print("Blocker report not found.")
                continue
            print(json.loads(path.read_text(encoding="utf-8")))
            continue

        print(f"Unknown command: {command}")
        _print_help()
