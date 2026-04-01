"""Custom LLM model routing by task type."""

from pathlib import Path
from typing import Any


class CustomLLMSupport:
    """Register custom models and choose them per task category."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.models: dict[str, dict[str, Any]] = {
            "general": {"provider": "openai", "model": "gpt-4o-mini", "cost_tier": "low"},
            "code": {"provider": "openai", "model": "gpt-5.3-codex", "cost_tier": "medium"},
            "review": {"provider": "openai", "model": "gpt-4.1", "cost_tier": "low"},
        }

    def register_model(self, task_type: str, provider: str, model: str, cost_tier: str = "medium") -> dict[str, Any]:
        """Register or override routing model for a task type."""
        key = task_type.strip().lower() or "general"
        self.models[key] = {
            "provider": provider.strip().lower() or "custom",
            "model": model.strip(),
            "cost_tier": cost_tier.strip().lower() or "medium",
        }
        return {"ok": True, "task_type": key, "config": self.models[key]}

    def choose_model(self, task: str) -> dict[str, Any]:
        """Choose best model based on task text classification."""
        task_type = self.classify_task(task)
        config = self.models.get(task_type, self.models["general"])
        return {
            "task": task,
            "task_type": task_type,
            "provider": config["provider"],
            "model": config["model"],
            "cost_tier": config["cost_tier"],
        }

    def classify_task(self, task: str) -> str:
        """Classify task into routing categories."""
        t = task.lower().strip()
        if any(word in t for word in ["fix", "refactor", "implement", "write", "code"]):
            return "code"
        if any(word in t for word in ["review", "security", "audit", "compliance"]):
            return "review"
        if any(word in t for word in ["summarize", "docs", "documentation", "explain"]):
            return "general"
        return "general"

    def list_models(self) -> dict[str, Any]:
        """List all configured model routes."""
        return {"count": len(self.models), "routes": self.models}
