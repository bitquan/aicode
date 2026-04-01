"""Learned preference and correction utilities for baseline learning loop."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _reports_dir(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    out_dir = root / ".autofix_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _pref_path(workspace_root: str) -> Path:
    return _reports_dir(workspace_root) / "learned_preferences.jsonl"


def _correction_path(workspace_root: str) -> Path:
    return _reports_dir(workspace_root) / "correction_events.jsonl"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return row


def add_preference(
    workspace_root: str,
    statement: str,
    category: str = "workflow",
    user_scope: str = "project",
    origin_prompt: str = "",
    confidence: float = 0.8,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Persist a learned preference row."""
    row: dict[str, Any] = {
        "preference_id": f"pref_{uuid4().hex[:12]}",
        "timestamp": _now_iso(),
        "user_scope": user_scope,
        "category": category,
        "statement": statement.strip(),
        "origin_prompt": origin_prompt,
        "confidence": float(confidence),
        "active": True,
        "supersedes": supersedes,
    }
    return _append_jsonl(_pref_path(workspace_root), row)


def get_preferences(workspace_root: str, active_only: bool = False) -> list[dict[str, Any]]:
    """Return preferences sorted oldest->newest."""
    rows = _read_jsonl(_pref_path(workspace_root))
    if active_only:
        rows = [row for row in rows if row.get("active", True)]
    return rows


def _write_preferences(workspace_root: str, rows: list[dict[str, Any]]) -> None:
    path = _pref_path(workspace_root)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _latest_active_preference_id(workspace_root: str) -> str | None:
    rows = get_preferences(workspace_root, active_only=True)
    if not rows:
        return None
    return str(rows[-1].get("preference_id"))


def apply_correction(
    workspace_root: str,
    correction_type: str,
    correction_text: str,
    target_preference_id: str | None = None,
) -> dict[str, Any]:
    """Apply correction event to a preference (replace/disable/strengthen)."""
    corr_type = correction_type.strip().lower()
    if corr_type not in {"replace", "disable", "strengthen"}:
        raise ValueError("correction_type must be replace|disable|strengthen")

    target_id = target_preference_id or _latest_active_preference_id(workspace_root)
    rows = get_preferences(workspace_root, active_only=False)
    updated = False
    matched_row: dict[str, Any] | None = None

    if target_id:
        for row in rows:
            if row.get("preference_id") == target_id:
                matched_row = row
                if corr_type in {"replace", "disable"}:
                    row["active"] = False
                if corr_type == "strengthen":
                    current = float(row.get("confidence", 0.8))
                    row["confidence"] = min(1.0, round(current + 0.1, 3))
                row["timestamp"] = _now_iso()
                updated = True
                break

    created_pref: dict[str, Any] | None = None
    if corr_type == "replace":
        if updated:
            _write_preferences(workspace_root, rows)
        inherited_category = str((matched_row or {}).get("category", "workflow"))
        created_pref = add_preference(
            workspace_root=workspace_root,
            statement=correction_text,
            category=inherited_category,
            user_scope="project",
            origin_prompt=f"correction:{corr_type}",
            confidence=0.9,
            supersedes=target_id,
        )
        rows = get_preferences(workspace_root, active_only=False)
        updated = True

    if updated and corr_type != "replace":
        _write_preferences(workspace_root, rows)

    correction_row: dict[str, Any] = {
        "correction_id": f"corr_{uuid4().hex[:12]}",
        "timestamp": _now_iso(),
        "target_preference_id": target_id,
        "correction_type": corr_type,
        "correction_text": correction_text,
        "applied": bool(updated),
    }
    _append_jsonl(_correction_path(workspace_root), correction_row)

    return {
        "correction": correction_row,
        "updated": updated,
        "target_preference_id": target_id,
        "created_preference": created_pref,
    }


def _intent_categories(request_intent: str) -> set[str]:
    intent = (request_intent or "").strip().lower()
    mapping: dict[str, set[str]] = {
        "generate": {"style", "testing", "safety", "tooling", "output_format", "workflow"},
        "autofix": {"testing", "safety", "tooling", "workflow"},
        "review": {"testing", "safety", "workflow"},
        "debug": {"testing", "tooling", "workflow"},
    }
    return mapping.get(intent, {"workflow", "output_format"})


def retrieve_preferences(
    workspace_root: str,
    request_intent: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve intent-aware top-k active preferences with dedupe."""
    allowed_categories = _intent_categories(request_intent)
    active_rows = get_preferences(workspace_root, active_only=True)

    candidates = [
        row
        for row in active_rows
        if str(row.get("category", "workflow")) in allowed_categories
    ]

    # Newest and strongest first.
    candidates.sort(
        key=lambda row: (
            float(row.get("confidence", 0.0)),
            str(row.get("timestamp", "")),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates:
        statement = str(row.get("statement", "")).strip()
        key = statement.lower()
        if not statement or key in seen:
            continue
        seen.add(key)
        selected.append(
            {
                "preference_id": row.get("preference_id"),
                "statement": statement,
                "category": row.get("category", "workflow"),
                "confidence": float(row.get("confidence", 0.0)),
                "retrieval_reason": f"intent={request_intent} category={row.get('category', 'workflow')}",
            }
        )
        if len(selected) >= top_k:
            break

    return selected


def read_correction_events(workspace_root: str, limit: int = 100) -> list[dict[str, Any]]:
    """Read recent correction events."""
    rows = _read_jsonl(_correction_path(workspace_root))
    return rows[-limit:]
