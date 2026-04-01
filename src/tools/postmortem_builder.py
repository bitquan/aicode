import json
from pathlib import Path

from src.tools.logger import load_audit_events


def generate_postmortem_from_blocker(workspace_root: str, trace_id: str) -> str:
    root = Path(workspace_root).resolve()
    blocker_path = root / ".autofix_reports" / f"{trace_id}.json"
    blocker = {}
    if blocker_path.exists():
        blocker = json.loads(blocker_path.read_text(encoding="utf-8"))

    events = load_audit_events(workspace_root, trace_id)

    out_dir = root / "docs" / "playbooks" / "incidents"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"postmortem_{trace_id}.md"

    lines = [
        f"# Postmortem: {trace_id}",
        "",
        "## Summary",
        f"- Target path: {blocker.get('target_path', 'unknown')}",
        f"- Stop reason: {blocker.get('stop_reason', 'unknown')}",
        f"- Attempts: {blocker.get('attempt_count', 0)}",
        f"- Failure categories: {', '.join(blocker.get('failure_categories', [])) or 'none'}",
        "",
        "## Timeline",
    ]

    if not events:
        lines.append("- No audit events found.")
    else:
        for idx, event in enumerate(events, start=1):
            lines.append(f"- {idx}. {event.get('event', 'unknown')} ({event.get('ts', '')})")

    lines.extend(
        [
            "",
            "## Root Cause",
            f"- Last failure: {blocker.get('last_failure', {}).get('summary', 'unknown')}",
            "",
            "## What Worked",
            "- Add specific successful mitigations here.",
            "",
            "## Preventive Actions",
            "- Strengthen tests around failing category.",
            "- Improve retrieval context quality for this target path.",
        ]
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
