"""Prompt-event logging for baseline learning telemetry."""

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from uuid import uuid4


def _events_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "prompt_events.jsonl"


def _output_traces_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "output_traces.jsonl"


def _retrieval_traces_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "retrieval_traces.jsonl"


def record_prompt_event(
    workspace_root: str,
    raw_prompt: str,
    intent: str,
    confidence: float,
    action_taken: str,
    result_status: str,
    source: str = "api",
    needs_external_research: bool = False,
    research_trigger_reason: str | None = None,
) -> dict[str, Any]:
    """Append one prompt event row to JSONL storage."""
    row: dict[str, Any] = {
        "id": f"evt_{uuid4().hex[:12]}",
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "raw_prompt": raw_prompt,
        "normalized_prompt": raw_prompt.strip().lower(),
        "intent": intent,
        "confidence": float(confidence),
        "needs_external_research": bool(needs_external_research),
        "research_trigger_reason": research_trigger_reason,
        "action_taken": action_taken,
        "result_status": result_status,
    }
    path = _events_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def record_output_trace(
    workspace_root: str,
    prompt_event_id: str,
    applied_preferences: list[str],
    tools_used: list[str],
    verification_summary: str | None = None,
    eval_summary: str | None = None,
) -> dict[str, Any]:
    """Append one output trace row to JSONL storage."""
    summary = verification_summary if verification_summary is not None else eval_summary if eval_summary is not None else "success"
    row: dict[str, Any] = {
        "output_id": f"out_{uuid4().hex[:12]}",
        "timestamp": datetime.now(UTC).isoformat(),
        "prompt_event_id": prompt_event_id,
        "applied_preferences": applied_preferences,
        "tools_used": tools_used,
        "verification_summary": summary,
        "eval_summary": summary,
    }
    path = _output_traces_path(workspace_root)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def record_retrieval_trace(
    workspace_root: str,
    request_intent: str,
    local_context_selected: list[dict[str, Any]],
    research_trigger_reason: str | None,
    selected_sources: list[dict[str, Any]],
    selected_preferences: list[str],
) -> dict[str, Any]:
    """Append one retrieval/research trace row to JSONL storage."""
    row: dict[str, Any] = {
        "trace_id": f"rtv_{uuid4().hex[:12]}",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_intent": request_intent,
        "local_context_selected": local_context_selected,
        "research_trigger_reason": research_trigger_reason,
        "selected_sources": selected_sources,
        "selected_preferences": selected_preferences,
    }
    path = _retrieval_traces_path(workspace_root)
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


def read_output_traces(workspace_root: str, limit: int = 100) -> list[dict[str, Any]]:
    """Read recent output traces (newest last)."""
    path = _output_traces_path(workspace_root)
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


def read_retrieval_traces(workspace_root: str, limit: int = 100) -> list[dict[str, Any]]:
    """Read recent retrieval/research traces (newest last)."""
    path = _retrieval_traces_path(workspace_root)
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
