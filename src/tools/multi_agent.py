"""Multi-agent collaboration planner built on router and shared memory."""

from __future__ import annotations

from typing import Dict, List

from src.tools.agent_memory import AgentMemoryStore
from src.tools.agent_router import AgentRouter


class MultiAgentCoordinator:
    """Creates collaboration plans and memory-aware execution hints."""

    def __init__(self, workspace_root: str = "."):
        self.router = AgentRouter()
        self.memory = AgentMemoryStore(workspace_root)

    def collaborate(self, task: str) -> Dict:
        route = self.router.route(task)
        memory_hits = self.memory.recall(topic=task)

        plan: List[str] = [
            f"{route['primary']} analyzes the task",
        ]
        for collaborator in route["collaborators"]:
            plan.append(f"{collaborator} contributes specialized feedback")
        plan.append("shared memory records useful results")
        plan.append("primary agent synthesizes final answer")

        return {
            "task": task,
            "primary": route["primary"],
            "collaborators": route["collaborators"],
            "plan": plan,
            "memory_hits": memory_hits.get("count", 0),
            "rationale": route["rationale"],
        }

    def record_outcome(self, task: str, summary: str, agents: List[str]) -> Dict:
        count = 0
        for agent in agents:
            self.memory.share(agent, task[:120], summary[:300])
            count += 1
        return {"status": "recorded", "shares": count}
