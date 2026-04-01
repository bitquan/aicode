"""Prompt-event logging for baseline learning telemetry."""

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def _events_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "prompt_events.jsonl"


def record_prompt_event(
    workspace_root: str,
    raw_prompt: str,
    intent: str,
    confidence: float,
    action_taken: str,
    result_status: str,
    source: str = "api",
) -> dict[str, Any]:
    """Append one prompt event row to JSONL storage."""
    row: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "raw_prompt": raw_prompt,
        "normalized_prompt": raw_prompt.strip().lower(),
        "intent": intent,
        "confidence": float(confidence),
        "action_taken": action_taken,
        "result_status": result_status,
    }
    path = _events_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def read_prompt_events(workspace_root: str, limit: int = 100) -> list[dict[str, Any]]:
    """Read recent prompt events (newest last)."""
    path = _events_path(workspace_root)
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]
