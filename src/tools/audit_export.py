from pathlib import Path

from src.tools.logger import load_audit_events


def export_audit_markdown(workspace_root: str, trace_id: str) -> str:
    events = load_audit_events(workspace_root, trace_id)
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{trace_id}.md"

    lines = [f"# Audit Export: {trace_id}", ""]
    for event in events:
        title = event.get("event", "unknown")
        ts = event.get("ts", "")
        lines.append(f"## {title} ({ts})")
        for key, value in event.items():
            if key in {"event", "ts"}:
                continue
            lines.append(f"- {key}: {value}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)
