"""Team Knowledge Base for shared developer learnings."""

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class TeamKnowledgeBase:
    """Centralized, lightweight team knowledge store."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self._dir = self.workspace_root / ".team_knowledge"
        self._path = self._dir / "knowledge.jsonl"

    def add_entry(
        self,
        topic: str,
        note: str,
        author: str = "chat",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a knowledge entry and return the stored record."""
        self._dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "author": author,
            "topic": topic.strip() or "general",
            "note": note.strip(),
            "tags": tags or [],
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        return entry

    def load_entries(self) -> list[dict[str, Any]]:
        """Load all entries from disk (newest first)."""
        if not self._path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        rows.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return rows

    def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Search entries by topic, note, author, or tags."""
        q = query.strip().lower()
        entries = self.load_entries()
        if not q:
            return {"query": query, "count": 0, "entries": []}

        matches: list[dict[str, Any]] = []
        for entry in entries:
            haystack = " ".join(
                [
                    str(entry.get("topic", "")),
                    str(entry.get("note", "")),
                    str(entry.get("author", "")),
                    " ".join(entry.get("tags", [])),
                ]
            ).lower()
            if q in haystack:
                matches.append(entry)
            if len(matches) >= limit:
                break

        return {"query": query, "count": len(matches), "entries": matches}

    def recent(self, limit: int = 10) -> dict[str, Any]:
        """Return most recent entries."""
        entries = self.load_entries()[:limit]
        return {"count": len(entries), "entries": entries}

    def stats(self) -> dict[str, Any]:
        """Return high-level KB statistics."""
        entries = self.load_entries()
        authors: dict[str, int] = {}
        topics: dict[str, int] = {}
        for entry in entries:
            authors[entry.get("author", "unknown")] = authors.get(entry.get("author", "unknown"), 0) + 1
            topics[entry.get("topic", "general")] = topics.get(entry.get("topic", "general"), 0) + 1

        top_topics = sorted(topics.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "total_entries": len(entries),
            "unique_authors": len(authors),
            "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
        }
