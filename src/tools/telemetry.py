import json
from pathlib import Path


def summarize_telemetry(workspace_root: str) -> dict:
    root = Path(workspace_root).resolve()
    audit_dir = root / ".autofix_reports" / "audit"
    trace_count = 0
    event_count = 0
    event_types = {}

    if audit_dir.exists():
        for path in audit_dir.glob("*.jsonl"):
            trace_count += 1
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event_count += 1
                event = json.loads(line).get("event", "unknown")
                event_types[event] = event_types.get(event, 0) + 1

    memory_path = root / ".autofix_reports" / "fix_memory.jsonl"
    memory_rows = 0
    memory_success = 0
    if memory_path.exists():
        for line in memory_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            memory_rows += 1
            row = json.loads(line)
            if row.get("success"):
                memory_success += 1

    return {
        "traces": trace_count,
        "events": event_count,
        "event_types": dict(sorted(event_types.items())),
        "fix_memory_rows": memory_rows,
        "fix_memory_success": memory_success,
    }
