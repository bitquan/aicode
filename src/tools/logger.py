import json
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4


def new_trace_id() -> str:
    return uuid4().hex[:12]


def log_event(event: str, trace_id: str, workspace_root: str | None = None, **fields):
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "trace_id": trace_id,
        "event": event,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False))
    if workspace_root:
        _append_audit_line(workspace_root, trace_id, payload)
    return payload


def get_audit_log_path(workspace_root: str, trace_id: str) -> str:
    root = Path(workspace_root).resolve()
    audit_dir = root / ".autofix_reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return str(audit_dir / f"{trace_id}.jsonl")


def load_audit_events(workspace_root: str, trace_id: str) -> list[dict]:
    path = Path(get_audit_log_path(workspace_root, trace_id))
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_audit_line(workspace_root: str, trace_id: str, payload: dict):
    path = Path(get_audit_log_path(workspace_root, trace_id))
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
