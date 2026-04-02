"""Continuous live-mode learning loop with optional unlockable slices."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.tools.doc_fetcher import DocFetcher
from src.tools.learning_events import read_prompt_events
from src.tools.project_memory import remember_note
from src.tools.self_builder import SelfBuilder


SLICE_CATALOG: dict[str, dict[str, Any]] = {
    "learn": {
        "points_required": 0,
        "description": "Continuously learn from prompt and result history.",
    },
    "research": {
        "points_required": 5,
        "description": "Build research hints from repeated prompt themes.",
    },
    "optimize": {
        "points_required": 12,
        "description": "Reserved for future autonomous optimization cycles.",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _state_path(workspace_root: str) -> Path:
    root = Path(workspace_root).resolve()
    kb_dir = root / ".knowledge_base"
    kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir / "live_mode_state.json"


def load_live_mode_state(workspace_root: str) -> dict[str, Any]:
    path = _state_path(workspace_root)
    if not path.exists():
        return {
            "enabled": False,
            "mode": "learning_only",
            "points": 0,
            "cycles": 0,
            "unlocked_slices": ["learn"],
            "last_cycle_at": None,
            "last_processed_event_id": None,
            "last_cycle_summary": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    state = {
        "enabled": bool(payload.get("enabled", False)),
        "mode": str(payload.get("mode", "learning_only")),
        "points": int(payload.get("points", 0)),
        "cycles": int(payload.get("cycles", 0)),
        "unlocked_slices": list(payload.get("unlocked_slices", ["learn"])),
        "last_cycle_at": payload.get("last_cycle_at"),
        "last_processed_event_id": payload.get("last_processed_event_id"),
        "last_cycle_summary": payload.get("last_cycle_summary", {}),
    }
    if "learn" not in state["unlocked_slices"]:
        state["unlocked_slices"].insert(0, "learn")
    return state


def save_live_mode_state(workspace_root: str, state: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(workspace_root)
    payload = {
        "enabled": bool(state.get("enabled", False)),
        "mode": str(state.get("mode", "learning_only")),
        "points": int(state.get("points", 0)),
        "cycles": int(state.get("cycles", 0)),
        "unlocked_slices": list(state.get("unlocked_slices", ["learn"])),
        "last_cycle_at": state.get("last_cycle_at"),
        "last_processed_event_id": state.get("last_processed_event_id"),
        "last_cycle_summary": state.get("last_cycle_summary", {}),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def unlock_slice(workspace_root: str, slice_name: str) -> dict[str, Any]:
    state = load_live_mode_state(workspace_root)
    if slice_name not in SLICE_CATALOG:
        return {
            "updated": False,
            "reason": f"unknown_slice:{slice_name}",
            "state": state,
        }
    if slice_name in state["unlocked_slices"]:
        return {
            "updated": False,
            "reason": "already_unlocked",
            "state": state,
        }
    state["unlocked_slices"].append(slice_name)
    return {
        "updated": True,
        "reason": "manually_unlocked",
        "state": save_live_mode_state(workspace_root, state),
    }


def _auto_unlock_slices(state: dict[str, Any]) -> list[str]:
    unlocked_now: list[str] = []
    points = int(state.get("points", 0))
    unlocked = set(state.get("unlocked_slices", []))
    for name, meta in SLICE_CATALOG.items():
        required = int(meta.get("points_required", 0))
        if points >= required and name not in unlocked:
            unlocked_now.append(name)
            unlocked.add(name)
    if unlocked_now:
        state["unlocked_slices"] = sorted(unlocked, key=lambda item: SLICE_CATALOG.get(item, {}).get("points_required", 0))
    return unlocked_now


def _events_to_learning_logs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for event in events:
        raw_prompt = str(event.get("raw_prompt", "")).strip()
        if not raw_prompt:
            continue
        status = str(event.get("result_status", ""))
        logs.append(
            {
                "query": raw_prompt,
                "action": str(event.get("action_taken", "unknown")),
                "success": status == "success",
                "doc_context": None,
            }
        )
    return logs


def _select_new_events(events: list[dict[str, Any]], last_processed_event_id: str | None) -> list[dict[str, Any]]:
    if not last_processed_event_id:
        return events

    for index, event in enumerate(events):
        if str(event.get("id", "")) == last_processed_event_id:
            return events[index + 1 :]

    return []


def _capture_research_hints(workspace_root: str, events: list[dict[str, Any]], limit: int = 3) -> dict[str, Any]:
    recent_prompts: list[str] = []
    for event in reversed(events):
        raw_prompt = str(event.get("raw_prompt", "")).strip()
        if raw_prompt and raw_prompt not in recent_prompts:
            recent_prompts.append(raw_prompt)
        if len(recent_prompts) >= limit:
            break

    if not recent_prompts:
        return {"notes_added": 0, "topics": []}

    fetcher = DocFetcher(workspace_root)
    packages = fetcher.extract_requirements(f"{workspace_root}/pyproject.toml")
    if not packages:
        packages = fetcher.extract_requirements(f"{workspace_root}/requirements.txt")
    if packages:
        fetcher.index_library(packages)

    notes_added = 0
    topics: list[str] = []
    for prompt in recent_prompts:
        docs = fetcher.get_relevant_docs(prompt, packages or None)
        if not docs:
            continue
        summary = docs[0]
        remember_note(
            workspace_root,
            key="live_research_hint",
            value=f"prompt={prompt[:120]} | hint={summary[:200]}",
        )
        notes_added += 1
        topics.append(prompt[:120])

    return {"notes_added": notes_added, "topics": topics}


def run_live_learning_cycle(
    workspace_root: str,
    *,
    allow_unlocked_slices: bool = False,
) -> dict[str, Any]:
    state = load_live_mode_state(workspace_root)
    events = read_prompt_events(workspace_root, limit=300)
    new_events = _select_new_events(events, str(state.get("last_processed_event_id") or "") or None)
    learning_logs = _events_to_learning_logs(new_events)

    builder = SelfBuilder(workspace_root)
    if learning_logs:
        builder.learn_from_logs(learning_logs)
        plan = builder.generate_self_improvement_plan(learning_logs)
    else:
        plan = {"status": "idle", "estimated_cycles": 0}

    last_processed_event_id = str(new_events[-1].get("id", "")) if new_events else state.get("last_processed_event_id")
    points_earned = 1 if learning_logs else 0

    result = {
        "events_observed": len(events),
        "new_events_observed": len(new_events),
        "logs_used": len(learning_logs),
        "learned": bool(learning_logs),
        "plan_status": plan.get("status", "ready"),
        "estimated_cycles": plan.get("estimated_cycles", 0),
        "slices_executed": ["learn"],
        "points_earned": points_earned,
        "last_processed_event_id": last_processed_event_id,
        "research_hints": {"notes_added": 0, "topics": []},
    }

    if allow_unlocked_slices and new_events:
        research_result = _capture_research_hints(workspace_root, new_events)
        if research_result.get("notes_added", 0) > 0:
            result["slices_executed"].append("research")
        result["research_hints"] = research_result

    return result


def run_live_mode(
    workspace_root: str,
    *,
    interval_seconds: int = 30,
    iterations: int = 0,
    allow_unlocked_slices: bool = False,
) -> dict[str, Any]:
    interval_seconds = max(1, int(interval_seconds))
    iterations = max(0, int(iterations))

    state = load_live_mode_state(workspace_root)
    state["enabled"] = True
    state["mode"] = "learning_only"
    save_live_mode_state(workspace_root, state)

    history: list[dict[str, Any]] = []
    cycle_count = 0
    stopped_by_user = False

    try:
        while True:
            cycle_count += 1
            current = load_live_mode_state(workspace_root)
            unlocked = set(current.get("unlocked_slices", ["learn"]))
            run_research = allow_unlocked_slices and "research" in unlocked

            cycle_result = run_live_learning_cycle(
                workspace_root,
                allow_unlocked_slices=run_research,
            )
            current["cycles"] = int(current.get("cycles", 0)) + 1
            current["points"] = int(current.get("points", 0)) + int(cycle_result.get("points_earned", 0))
            current["last_cycle_at"] = _utc_now_iso()
            current["last_processed_event_id"] = cycle_result.get("last_processed_event_id")
            current["last_cycle_summary"] = cycle_result
            unlocked_now = _auto_unlock_slices(current)
            save_live_mode_state(workspace_root, current)

            history.append(
                {
                    "cycle": cycle_count,
                    "points": current["points"],
                    "unlocked_now": unlocked_now,
                    **cycle_result,
                }
            )

            if iterations and cycle_count >= iterations:
                break

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        stopped_by_user = True
    finally:
        final_state = load_live_mode_state(workspace_root)
        final_state["enabled"] = False
        save_live_mode_state(workspace_root, final_state)

    return {
        "mode": "learning_only",
        "iterations_requested": iterations,
        "iterations_run": cycle_count,
        "allow_unlocked_slices": allow_unlocked_slices,
        "stopped_by_user": stopped_by_user,
        "history": history,
        "final_state": load_live_mode_state(workspace_root),
    }
