from src.tools.telemetry import summarize_telemetry


def generate_release_notes(workspace_root: str, version: str) -> str:
    summary = summarize_telemetry(workspace_root)
    lines = [
        f"## Release {version}",
        "",
        "### Runtime Summary",
        f"- Traces recorded: {summary['traces']}",
        f"- Events recorded: {summary['events']}",
        f"- Fix-memory entries: {summary['fix_memory_rows']} ({summary['fix_memory_success']} successful)",
        "",
        "### Event Breakdown",
    ]
    for name, count in summary["event_types"].items():
        lines.append(f"- {name}: {count}")
    return "\n".join(lines)
