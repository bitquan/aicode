from pathlib import Path

from src.tools.logger import load_audit_events


def build_incident_timeline(workspace_root: str, trace_id: str) -> list[dict]:
    events = load_audit_events(workspace_root, trace_id)
    timeline = []
    for idx, event in enumerate(events, start=1):
        timeline.append(
            {
                "step": idx,
                "ts": event.get("ts", ""),
                "event": event.get("event", "unknown"),
                "trace_id": event.get("trace_id", trace_id),
            }
        )
    return timeline


def generate_incident_report(workspace_root: str, trace_id: str) -> str:
    timeline = build_incident_timeline(workspace_root, trace_id)
    root = Path(workspace_root).resolve()
    out_dir = root / "docs" / "playbooks" / "incidents"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"incident_{trace_id}.md"

    lines = [f"# Incident Report: {trace_id}", "", "## Timeline"]
    if not timeline:
        lines.append("- No events found for this trace.")
    else:
        for row in timeline:
            lines.append(f"- {row['step']}. {row['event']} ({row['ts']})")

    lines.extend(
        [
            "",
            "## Impact",
            "- Describe observed impact.",
            "",
            "## Mitigation",
            "- Describe mitigation applied.",
            "",
            "## Follow-up",
            "- Add corrective and preventive actions.",
        ]
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
