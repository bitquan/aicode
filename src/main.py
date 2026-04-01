import sys
import json
from pathlib import Path

from src.agents.coding_agent import CodingAgent
from src.tools.autofix import run_autofix_loop
from src.tools.fix_memory import retrieve_similar_fixes
from src.tools.logger import load_audit_events
from src.tools.patch_applier import preview_diff, apply_file_edit
from src.ui.terminal_ui import run_terminal_ui


def _print_usage():
    print("Usage:")
    print("  python -m src.main \"<coding prompt>\"")
    print("  python -m src.main edit <relative_path> \"<instruction>\" [--yes]")
    print("  python -m src.main capabilities")
    print("  python -m src.main plan \"<request>\"")
    print("  python -m src.main tui")
    print("  python -m src.main autofix <relative_path> \"<instruction>\" [--tests \"<cmd>\"] [--max-attempts N] [--multi] [--no-flaky-confirm]")
    print("  python -m src.main audit <trace_id>")
    print("  python -m src.main memory <target_path> <failure_category>")
    print("  python -m src.main blocker <trace_id>")

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

    generated_code = agent.generate_code(prompt)
    print("\nGenerated Code:\n")
    print(generated_code)

    evaluation_result = agent.evaluate_code(generated_code)
    print("\nEvaluation Result:\n")
    print(evaluation_result)

if __name__ == "__main__":
    main()