"""Self-improvement readiness canaries for live routing and self-awareness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config.runtime_manifest import load_runtime_manifest

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


def load_readiness_canaries(config_path: str | None = None) -> list[dict[str, Any]]:
    """Load canned prompts that verify live routing and runtime awareness."""
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).resolve().parents[1] / "config" / "readiness_canaries.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def run_engine_readiness_suite(engine: "ChatEngine") -> dict[str, Any]:
    """Run canary prompts against the current in-memory engine."""
    manifest = load_runtime_manifest()
    awareness = engine.get_self_awareness_snapshot()
    results: list[dict[str, Any]] = []

    for canary in load_readiness_canaries():
        prompt = str(canary.get("prompt", "")).strip()
        request = engine.parse_request_model(prompt)
        response = engine.execute_request(request)

        expected_action = str(canary.get("expected_action", ""))
        required = [str(item) for item in canary.get("response_must_include", [])]
        action_ok = response.action == expected_action
        contains_ok = all(item in response.text for item in required)
        passed = action_ok and contains_ok

        results.append(
            {
                "name": canary.get("name", prompt[:40] or "unnamed"),
                "prompt": prompt,
                "expected_action": expected_action,
                "actual_action": response.action,
                "passed": passed,
                "missing_response_markers": [item for item in required if item not in response.text],
                "response_preview": response.text[:240],
            }
        )

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "status": "pass" if passed == total else "fail",
        "passed": passed,
        "failed": total - passed,
        "total": total,
        "routing_generation": manifest.get("routing_generation"),
        "readiness_suite_version": manifest.get("readiness_suite_version"),
        "server_reachable": bool(awareness.get("server", {}).get("reachable", False)),
        "ollama_reachable": bool(awareness.get("ollama", {}).get("reachable", False)),
        "web_enabled": bool(awareness.get("web", {}).get("enabled", False)),
        "known_vscode_panel": awareness.get("known_surfaces", {}).get("vscode_panel", ""),
        "results": results,
    }
