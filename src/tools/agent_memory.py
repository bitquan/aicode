"""Shared memory for multiple specialized agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


class AgentMemoryStore:
    """Persists shared memory entries for collaborating agents."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.memory_path = self.workspace_root / ".knowledge_base" / "agent_memory.json"
        self.memory_path.parent.mkdir(exist_ok=True)
        self.data = self._load()

    def _load(self) -> Dict:
        if self.memory_path.exists():
            try:
                with open(self.memory_path) as handle:
                    return json.load(handle)
            except Exception:
                pass
        return {"entries": []}

    def _save(self) -> None:
        with open(self.memory_path, "w") as handle:
            json.dump(self.data, handle, indent=2)

    def share(self, agent: str, topic: str, note: str) -> Dict:
        entry = {
            "agent": agent,
            "topic": topic,
            "note": note,
        }
        self.data.setdefault("entries", []).append(entry)
        self._save()
        return {"status": "shared", "entries": len(self.data["entries"])}

    def recall(self, topic: Optional[str] = None, agent: Optional[str] = None) -> Dict:
        entries = self.data.get("entries", [])
        filtered: List[Dict] = []
        for entry in entries:
            if topic and topic.lower() not in entry.get("topic", "").lower() and topic.lower() not in entry.get("note", "").lower():
                continue
            if agent and agent != entry.get("agent"):
                continue
            filtered.append(entry)
        return {"count": len(filtered), "entries": filtered[:20]}

    def snapshot(self) -> Dict:
        entries = self.data.get("entries", [])
        agents = sorted({entry.get("agent", "unknown") for entry in entries})
        return {
            "entries": len(entries),
            "agents": agents,
        }
