"""Framework-specific expert assistant."""

from pathlib import Path
from typing import Any


_FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "django": ["django"],
    "fastapi": ["fastapi", "uvicorn"],
    "flask": ["flask"],
    "react": ["react", "next", "nextjs"],
    "vue": ["vue", "nuxt"],
}

_EXPERT_TIPS: dict[str, list[str]] = {
    "django": [
        "Run migrations after model changes and keep migration files reviewed.",
        "Use `select_related`/`prefetch_related` to reduce query counts.",
        "Keep settings split by environment and avoid hardcoded secrets.",
    ],
    "fastapi": [
        "Use Pydantic models for request/response validation.",
        "Prefer dependency injection for auth, DB sessions, and shared services.",
        "Define explicit response models and status codes for stable APIs.",
    ],
    "flask": [
        "Use application factory pattern for testability.",
        "Avoid global mutable state; keep extensions initialized cleanly.",
        "Centralize error handling with structured JSON responses for APIs.",
    ],
    "react": [
        "Split components by responsibility and keep state close to usage.",
        "Use memoization thoughtfully for expensive derived values.",
        "Keep side effects in hooks with deterministic dependencies.",
    ],
    "vue": [
        "Prefer composables for reusable logic over large monolithic components.",
        "Keep props/events contracts explicit for component boundaries.",
        "Use route-level code splitting for performance.",
    ],
}


class FrameworkExperts:
    """Detect frameworks and provide practical expert guidance."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def detect_frameworks(self) -> dict[str, Any]:
        """Detect likely frameworks from dependency manifests."""
        blob = "\n".join(self._read_manifests()).lower()
        found: list[str] = []
        for framework, patterns in _FRAMEWORK_PATTERNS.items():
            if any(pattern in blob for pattern in patterns):
                found.append(framework)

        return {
            "count": len(found),
            "frameworks": sorted(found),
            "status": "FOUND" if found else "NONE",
        }

    def expert_advice(self, framework: str, question: str = "") -> dict[str, Any]:
        """Return framework-specific tips and optional question context."""
        key = framework.strip().lower()
        tips = _EXPERT_TIPS.get(key)
        if not tips:
            return {"error": f"Unsupported framework: {framework}"}

        focus = self._infer_focus(question)
        return {
            "framework": key,
            "question": question,
            "focus": focus,
            "tips": tips,
        }

    def recommend_expert(self, task: str) -> dict[str, Any]:
        """Recommend framework expert mode based on task text + detected frameworks."""
        text = task.lower().strip()
        detected = self.detect_frameworks().get("frameworks", [])

        for framework in _FRAMEWORK_PATTERNS:
            if framework in text:
                return {"framework": framework, "reason": "explicit mention", "task": task}

        if detected:
            return {"framework": detected[0], "reason": "detected in repository", "task": task}

        return {"framework": "fastapi", "reason": "default recommendation", "task": task}

    def _read_manifests(self) -> list[str]:
        paths = [
            self.workspace_root / "requirements.txt",
            self.workspace_root / "pyproject.toml",
            self.workspace_root / "package.json",
        ]
        blobs: list[str] = []
        for path in paths:
            if path.exists():
                try:
                    blobs.append(path.read_text(encoding="utf-8"))
                except OSError:
                    continue
        return blobs

    def _infer_focus(self, question: str) -> str:
        q = question.lower()
        if any(word in q for word in ["performance", "slow", "latency"]):
            return "performance"
        if any(word in q for word in ["security", "auth", "permission"]):
            return "security"
        if any(word in q for word in ["test", "coverage", "qa"]):
            return "testing"
        return "general"
