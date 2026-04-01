"""Architecture Diagram Understanding utilities."""

import re
from pathlib import Path
from typing import Any


_EDGE_RE = re.compile(r"([A-Za-z0-9_]+)\s*(?:-->|->|==>|=>)\s*([A-Za-z0-9_]+)")
_NODE_LABEL_RE = re.compile(r"([A-Za-z0-9_]+)\s*\[(.*?)\]")


class ArchitectureDiagramUnderstanding:
    """Analyze simple Mermaid-like architecture diagrams."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def analyze_text(self, diagram_text: str) -> dict[str, Any]:
        """Analyze diagram text and return flow summary."""
        edges = []
        nodes = set()
        labels: dict[str, str] = {}

        for line in diagram_text.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("%%"):
                continue

            label_match = _NODE_LABEL_RE.search(clean)
            if label_match:
                labels[label_match.group(1)] = label_match.group(2)

            edge_match = _EDGE_RE.search(clean)
            if edge_match:
                source, target = edge_match.group(1), edge_match.group(2)
                edges.append({"from": source, "to": target})
                nodes.add(source)
                nodes.add(target)

        indegree: dict[str, int] = {node: 0 for node in nodes}
        outdegree: dict[str, int] = {node: 0 for node in nodes}
        for edge in edges:
            outdegree[edge["from"]] += 1
            indegree[edge["to"]] += 1

        entry_points = sorted([node for node in nodes if indegree[node] == 0])
        terminal_nodes = sorted([node for node in nodes if outdegree[node] == 0])

        return {
            "nodes": sorted(nodes),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "edges": edges,
            "entry_points": entry_points,
            "terminal_nodes": terminal_nodes,
            "labels": labels,
            "status": "OK" if nodes else "NO_GRAPH",
        }

    def analyze_file(self, file_path: str) -> dict[str, Any]:
        """Analyze a diagram file relative to workspace root."""
        path = self.workspace_root / file_path
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        text = path.read_text(encoding="utf-8")
        result = self.analyze_text(text)
        result["file"] = file_path
        return result

    def flow_summary(self, result: dict[str, Any]) -> list[str]:
        """Return concise natural-language flow summary lines."""
        if result.get("status") == "NO_GRAPH":
            return ["No edges found in diagram."]

        lines = [
            f"Nodes: {result.get('node_count', 0)}",
            f"Connections: {result.get('edge_count', 0)}",
            f"Entry points: {', '.join(result.get('entry_points', [])) or 'none'}",
            f"Terminal nodes: {', '.join(result.get('terminal_nodes', [])) or 'none'}",
        ]
        for edge in result.get("edges", [])[:5]:
            lines.append(f"Flow: {edge['from']} -> {edge['to']}")
        return lines
