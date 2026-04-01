from pathlib import Path
from datetime import datetime, UTC


def create_snapshot(workspace_root: str, relative_path: str) -> str:
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    snapshots = root / ".autofix_reports" / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out = snapshots / f"{relative_path.replace('/', '__')}__{stamp}.bak"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    return str(out)


def rollback_snapshot(workspace_root: str, relative_path: str, snapshot_path: str):
    root = Path(workspace_root).resolve()
    target = (root / relative_path).resolve()
    snapshot = Path(snapshot_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(snapshot.read_text(encoding="utf-8"), encoding="utf-8")
