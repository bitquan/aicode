"""Prompt taxonomy for baseline intent coverage."""

import re
from typing import Any


TOP_20_INTENT_TAXONOMY: dict[str, list[str]] = {
    "greeting": ["hey", "hi", "hello"],
    "capabilities": ["what can you do", "capabilities", "help"],
    "repo_summary": ["about this repo", "this repository", "project overview", "repo summary"],
    "status": ["status", "progress", "health", "score"],
    "search": ["search", "find", "where"],
    "browse": ["browse", "open", "ls", "show"],
    "generate": ["write", "generate", "create"],
    "edit": ["add", "edit", "update"],
    "autofix": ["fix", "autofix", "repair"],
    "review": ["review", "audit"],
    "debug": ["debug", "trace", "breakpoint"],
    "profile": ["profile", "optimize"],
    "coverage": ["coverage", "test coverage"],
    "security": ["security scan", "vulnerability"],
    "docs": ["generate docs", "docstrings"],
    "api": ["generate api", "create api"],
    "deps": ["dependencies", "dep resolve"],
    "cost": ["optimize cost", "cost report"],
    "learning": ["learn:", "teach:", "remember this", "note:"],
    "analytics": ["team analytics", "dashboard"],
}


def classify_prompt_type(prompt: str) -> dict[str, Any]:
    """Classify prompt into one of the top intent categories."""
    lower = prompt.strip().lower()

    def matches(signal: str) -> bool:
        sig = signal.lower()
        if not sig:
            return False
        if " " in sig or ":" in sig:
            return sig in lower
        return re.search(rf"\b{re.escape(sig)}\b", lower) is not None

    for intent, signals in TOP_20_INTENT_TAXONOMY.items():
        matched = next((signal for signal in signals if matches(signal)), None)
        if matched is not None:
            return {"intent": intent, "matched_signal": matched}
    return {"intent": "unknown", "matched_signal": None}
