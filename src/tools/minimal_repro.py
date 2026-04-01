from pathlib import Path


def write_minimal_repro(workspace_root: str, trace_id: str, target_path: str, instruction: str, test_command: str, last_failure: dict):
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{trace_id}_repro.md"

    content = [
        "# Minimal Repro",
        "",
        f"- Trace ID: {trace_id}",
        f"- Target file: {target_path}",
        f"- Instruction: {instruction}",
        f"- Test command: {test_command}",
        f"- Failure category: {last_failure.get('category', 'unknown')}",
        f"- Failure summary: {last_failure.get('summary', 'N/A')}",
        "",
        "## Steps",
        "1. Ensure project virtualenv is active.",
        f"2. Run: `{test_command}`",
        "3. Observe failing output.",
        "4. Re-run autofix with stronger context if needed.",
    ]

    nodeids = last_failure.get("pytest_nodeids", [])
    if nodeids:
        content.extend([
            "",
            "## Pytest Focused Repro",
            "Use one of these focused reruns:",
        ])
        for nodeid in nodeids[:10]:
            content.append(f"- python -m pytest -q {nodeid}")

    out_path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return str(out_path)
