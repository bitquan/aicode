"""Task router for specialized agent selection."""

from __future__ import annotations

from typing import Dict, List


class AgentRouter:
    """Routes tasks to a primary agent and optional collaborators."""

    def route(self, task: str) -> Dict:
        lower = task.lower()
        primary = "generator"
        collaborators: List[str] = []
        rationale = []

        if any(word in lower for word in ["test", "coverage", "assert"]):
            primary = "tester"
            collaborators.append("generator")
            rationale.append("testing keywords detected")
        if any(word in lower for word in ["doc", "readme", "document", "comment"]):
            primary = "documenter"
            collaborators.append("generator")
            rationale.append("documentation keywords detected")
        if any(word in lower for word in ["fix", "bug", "repair", "error"]):
            primary = "repairer"
            collaborators.extend(["tester", "generator"])
            rationale.append("repair keywords detected")
        if any(word in lower for word in ["review", "security", "quality"]):
            primary = "reviewer"
            collaborators.append("generator")
            rationale.append("review keywords detected")

        deduped = []
        for item in collaborators:
            if item != primary and item not in deduped:
                deduped.append(item)

        return {
            "primary": primary,
            "collaborators": deduped,
            "rationale": rationale or ["default generation workflow"],
        }
