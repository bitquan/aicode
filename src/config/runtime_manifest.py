"""Shared runtime manifest helpers for server, CLI, and extension diagnostics."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_runtime_manifest(config_path: str | None = None) -> dict[str, Any]:
    """Load static runtime metadata shared across surfaces."""
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).with_name("runtime_manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def build_runtime_metadata(
    *,
    workspace_root: str,
    started_at: str,
    pid: int,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Build runtime metadata for a live process from the shared manifest."""
    manifest = load_runtime_manifest(config_path)
    workspace = Path(workspace_root).resolve()
    git_commit = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
        git_commit = result.stdout.strip()
    except Exception:
        git_commit = ""

    return {
        **manifest,
        "started_at": started_at,
        "pid": pid,
        "git_commit": git_commit,
        "workspace_root": str(workspace),
    }


def utc_now_iso() -> str:
    """Return a stable ISO-8601 UTC timestamp for runtime metadata."""
    return datetime.now(timezone.utc).isoformat()
