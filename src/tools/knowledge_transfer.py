"""Knowledge base export/import helpers for sharing learned data across projects."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


class KnowledgeTransfer:
    """Exports and imports `.knowledge_base` content."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.kb_dir = self.workspace_root / ".knowledge_base"
        self.kb_dir.mkdir(exist_ok=True)

    def export_bundle(self, output_path: str = "knowledge_export.json") -> Dict:
        """Export all JSON knowledge files into a single bundle."""
        target = self.workspace_root / output_path

        bundle = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "workspace": str(self.workspace_root.name),
            "files": {},
        }

        for json_file in sorted(self.kb_dir.glob("*.json")):
            try:
                with open(json_file) as handle:
                    bundle["files"][json_file.name] = json.load(handle)
            except Exception:
                bundle["files"][json_file.name] = {}

        with open(target, "w") as handle:
            json.dump(bundle, handle, indent=2)

        return {
            "status": "exported",
            "path": str(target.relative_to(self.workspace_root)),
            "file_count": len(bundle["files"]),
        }

    def import_bundle(self, bundle_path: str, merge: bool = True) -> Dict:
        """Import a previously exported bundle into local knowledge base."""
        source = Path(bundle_path)
        if not source.is_absolute():
            source = self.workspace_root / source

        if not source.exists():
            return {"error": f"Bundle not found: {bundle_path}"}

        with open(source) as handle:
            bundle = json.load(handle)

        files = bundle.get("files", {})
        imported = 0

        for filename, payload in files.items():
            target = self.kb_dir / filename
            if merge and target.exists():
                try:
                    with open(target) as current_handle:
                        current_payload = json.load(current_handle)
                except Exception:
                    current_payload = {}

                merged = self._merge_dicts(current_payload, payload)
                with open(target, "w") as handle:
                    json.dump(merged, handle, indent=2)
            else:
                with open(target, "w") as handle:
                    json.dump(payload, handle, indent=2)
            imported += 1

        return {
            "status": "imported",
            "bundle": str(source.relative_to(self.workspace_root) if str(source).startswith(str(self.workspace_root)) else source),
            "imported_files": imported,
        }

    def list_knowledge_files(self) -> Dict:
        """List known knowledge files and file sizes."""
        items: List[Dict] = []
        for json_file in sorted(self.kb_dir.glob("*.json")):
            items.append({
                "name": json_file.name,
                "size": json_file.stat().st_size,
            })

        return {
            "count": len(items),
            "files": items,
        }

    def _merge_dicts(self, base: Dict, incoming: Dict) -> Dict:
        """Shallow-recursive merge for JSON payloads."""
        merged = dict(base)
        for key, value in incoming.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged
