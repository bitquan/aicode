"""Shared repo-research helpers used by handlers and self-improvement flows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.tools.doc_fetcher import DOC_SOURCES, DocFetcher, enhance_with_docs
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


RESEARCH_SURFACES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("VS Code panel", "vscode-extension/src/extension.ts", ("panel", "chat panel", "inline chat", "history", "button", "extension")),
    ("Extension manifest", "vscode-extension/package.json", ("command", "commands", "menu", "palette", "extension")),
    ("Server API", "src/server.py", ("server", "api", "endpoint", "health", "stream", "ollama")),
    ("Shared request parser", "src/tools/commanding/request_parser.py", ("parser", "routing", "route", "intent", "clarify", "research")),
    ("Shared dispatcher", "src/tools/commanding/dispatcher.py", ("dispatcher", "registry", "action", "command")),
    ("App service", "src/app_service.py", ("api", "service", "surface", "command")),
)

TARGETED_TEST_COMMANDS: dict[str, list[str]] = {
    "src/app_service.py": [
        "./.venv/bin/python -m pytest -q tests/test_app_service.py tests/test_server_app_command.py",
    ],
    "src/server.py": [
        "./.venv/bin/python -m pytest -q tests/test_server.py tests/test_server_app_command.py",
    ],
    "src/tools/chat_engine.py": [
        "./.venv/bin/python -m pytest -q tests/test_chat_engine.py tests/test_chat_help_summary.py tests/test_self_build_chat.py",
    ],
    "src/tools/self_improve.py": [
        "./.venv/bin/python -m pytest -q tests/test_self_improve.py tests/test_self_build_chat.py tests/test_self_improve_controller.py",
    ],
    "src/tools/commanding/request_parser.py": [
        "./.venv/bin/python -m pytest -q tests/test_chat_help_summary.py tests/test_routing_regression_buckets.py tests/test_app_service.py",
    ],
    "src/tools/commanding/dispatcher.py": [
        "./.venv/bin/python -m pytest -q tests/test_app_service.py tests/test_server_app_command.py",
    ],
    "src/tools/commanding/handlers/repo.py": [
        "./.venv/bin/python -m pytest -q tests/test_readiness_suite.py tests/test_server.py tests/test_chat_engine.py",
    ],
    "vscode-extension/src/extension.ts": [
        "npm --prefix vscode-extension run compile",
        "npm --prefix vscode-extension run test:smoke",
    ],
    "vscode-extension/src/runtime_support.ts": [
        "npm --prefix vscode-extension run compile",
        "npm --prefix vscode-extension run test:smoke",
    ],
}

FULL_SUITE_TARGETS = {
    "src/app_service.py",
    "src/server.py",
    "src/tools/chat_engine.py",
    "src/tools/commanding/request_parser.py",
    "src/tools/commanding/dispatcher.py",
}


def _query_keywords(query: str) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "into",
        "that",
        "this",
        "from",
        "your",
        "have",
        "make",
        "build",
        "create",
        "add",
        "please",
        "could",
        "would",
        "should",
    }
    tokens = re.findall(r"[a-z0-9_+-]+", query.lower())
    return [token for token in tokens if len(token) > 2 and token not in stopwords]


def _score_path(path: str, keywords: list[str]) -> int:
    lower = path.lower()
    score = 0
    for keyword in keywords:
        if keyword in lower:
            score += 2
        elif keyword.rstrip("s") in lower:
            score += 1
    return score


def _iter_index_paths(index: Any) -> list[str]:
    if isinstance(index, list):
        return [str(entry.get("path", "")) for entry in index if isinstance(entry, dict)]
    if isinstance(index, dict):
        return [str(key) for key in index.keys()]
    return []


def _commands_for_path(path: str) -> list[str]:
    if path in TARGETED_TEST_COMMANDS:
        return TARGETED_TEST_COMMANDS[path]

    normalized = path.replace("\\", "/")
    stem = normalized.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if normalized.startswith("src/"):
        direct_test = f"tests/test_{stem}.py"
        repo_root = Path(__file__).resolve().parents[2]
        if (repo_root / direct_test).exists():
            return [f"./.venv/bin/python -m pytest -q {direct_test}"]
        return []
    if normalized.startswith("vscode-extension/"):
        return ["npm --prefix vscode-extension run compile"]
    return []


def _needs_full_regression(paths: list[str], targeted_commands: list[str]) -> bool:
    if not targeted_commands:
        return True
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized in FULL_SUITE_TARGETS:
            return True
        if normalized.startswith("src/tools/commanding/"):
            return True
    return False


def build_verification_plan(paths: list[str]) -> dict[str, Any]:
    targeted_commands: list[str] = []
    seen: set[str] = set()
    for path in paths:
        for command in _commands_for_path(path):
            if command in seen:
                continue
            seen.add(command)
            targeted_commands.append(command)

    steps: list[dict[str, str]] = []
    for command in targeted_commands:
        steps.append({"kind": "command", "label": "targeted", "command": command})

    steps.append({"kind": "readiness", "label": "readiness", "command": "GET /v1/aicode/readiness"})

    if _needs_full_regression(paths, targeted_commands):
        steps.append(
            {
                "kind": "command",
                "label": "full",
                "command": "./.venv/bin/python -m pytest -q",
            }
        )

    return {
        "steps": steps,
        "descriptions": [
            step["command"] if step["kind"] == "command" else "Run readiness canaries"
            for step in steps
        ],
    }


def _select_doc_sources(workspace_root: str, goal: str) -> list[dict[str, str]]:
    """Return authoritative doc sources most relevant to a research goal."""
    fetcher = DocFetcher(workspace_root)
    packages = fetcher.extract_requirements(f"{workspace_root}/pyproject.toml")
    if not packages:
        packages = fetcher.extract_requirements(f"{workspace_root}/requirements.txt")

    goal_lower = goal.lower()
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for package in packages:
        url = DOC_SOURCES.get(package)
        if not url or url in seen:
            continue
        if package in goal_lower or not selected:
            seen.add(url)
            selected.append(
                {
                    "label": f"{package} docs",
                    "url": url,
                    "reason": "official project documentation",
                }
            )
        if len(selected) >= 3:
            break
    return selected


def build_research_payload(
    engine: "ChatEngine",
    goal: str,
    *,
    prefer_web: bool = False,
    max_results: int = 5,
) -> dict[str, Any]:
    """Return structured repo research for a change goal."""
    goal = goal.strip() or "general repository research"
    keywords = _query_keywords(goal)
    awareness = engine.get_self_awareness_snapshot()
    web = awareness["web"]

    index = engine.context.get("index", [])
    if not index:
        index = build_file_index(str(engine.workspace_root))
        engine.context["index"] = index

    ranked_paths: list[tuple[int, str, str]] = []
    for label, path, hints in RESEARCH_SURFACES:
        score = _score_path(path, keywords)
        score += sum(3 for hint in hints if hint in goal.lower())
        if score:
            ranked_paths.append((score, path, label))

    for path in _iter_index_paths(index):
        score = _score_path(path, keywords)
        if score:
            ranked_paths.append((score, path, "repo match"))

    try:
        snippets = retrieve_relevant_snippets(str(engine.workspace_root), goal, limit=4)
    except Exception:
        snippets = []
    for snippet in snippets:
        path = str(snippet.get("path", ""))
        if path:
            ranked_paths.append((max(3, _score_path(path, keywords)), path, "semantic match"))

    likely_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, path, reason in sorted(ranked_paths, key=lambda item: (-item[0], item[1])):
        if path in seen:
            continue
        seen.add(path)
        likely_files.append({"path": path, "reason": reason, "score": score})
        if len(likely_files) >= max_results:
            break

    web_context = ""
    selected_sources: list[dict[str, str]] = []
    if prefer_web and web["enabled"]:
        web_context = enhance_with_docs(str(engine.workspace_root), goal)
        if web_context:
            selected_sources = _select_doc_sources(str(engine.workspace_root), goal)

    verification = build_verification_plan([item["path"] for item in likely_files[:3]])
    return {
        "goal": goal,
        "workflow": "research → identify files → edit/apply change",
        "known_surfaces": awareness["known_surfaces"],
        "server": awareness["server"],
        "ollama": awareness["ollama"],
        "web": web,
        "web_research_used": bool(web_context),
        "web_context": web_context,
        "selected_sources": selected_sources,
        "likely_files": likely_files,
        "verification_plan": verification["descriptions"],
        "verification_plan_steps": verification["steps"],
    }


def render_research_summary(payload: dict[str, Any]) -> str:
    """Render structured research payload for conversational surfaces."""
    web = payload["web"]
    likely_files = payload.get("likely_files", [])
    lines = [
        "🔎 Research Summary",
        f"  • Goal: {payload.get('goal', 'general repository research')}",
        f"  • Suggested workflow: {payload.get('workflow', 'research → identify files → edit/apply change')}",
        f"  • VS Code panel source: {payload['known_surfaces']['vscode_panel']}",
        f"  • Server: {'up' if payload['server']['reachable'] else 'down'} at {payload['server']['url']}",
        f"  • Ollama: {'reachable' if payload['ollama']['reachable'] else 'unreachable'} at {payload['ollama']['url']}",
        f"  • Web research: {web['summary']}",
    ]

    if not likely_files:
        lines.extend(
            [
                "  • I couldn't identify a strong file target yet.",
                "  • Next step: try naming the surface, file, or user-visible area you want changed.",
            ]
        )
        return "\n".join(lines)

    lines.append("  • Likely files:")
    for item in likely_files:
        lines.append(f"    - {item['path']} ({item['reason']})")

    lines.append("  • Expected verification:")
    for item in payload.get("verification_plan", []):
        lines.append(f"    - {item}")

    if payload.get("web_context"):
        lines.append("")
        lines.append(str(payload["web_context"]))
    if payload.get("selected_sources"):
        lines.append("  • Sources:")
        for source in payload["selected_sources"][:3]:
            lines.append(f"    - {source.get('label')}: {source.get('url')}")

    lines.append("")
    lines.append("  • Proposed next step: I can patch the likely files above directly.")
    return "\n".join(lines)
