import json
from pathlib import Path


def _state_path(workspace_root: str, trace_id: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports" / "state"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{trace_id}.json"


def save_autofix_state(workspace_root: str, trace_id: str, payload: dict) -> str:
    path = _state_path(workspace_root, trace_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def load_autofix_state(workspace_root: str, trace_id: str) -> dict | None:
    path = _state_path(workspace_root, trace_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
