from datetime import datetime, UTC, timedelta
from pathlib import Path


def cleanup_reports(workspace_root: str, older_than_days: int = 14) -> dict:
    root = Path(workspace_root).resolve()
    report_root = root / ".autofix_reports"
    if not report_root.exists():
        return {"deleted": 0, "paths": []}

    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    deleted = []

    for path in report_root.rglob("*"):
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if mtime < cutoff:
            deleted.append(str(path))
            path.unlink(missing_ok=True)

    return {"deleted": len(deleted), "paths": deleted}
