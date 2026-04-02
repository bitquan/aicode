"""Repository, dashboard, and analysis handlers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from src.tools.doc_fetcher import enhance_with_docs
from src.tools.project_memory import remember_note
from src.tools.readiness_suite import run_engine_readiness_suite
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.status_report import build_status_report

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


def _handle_search(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Search codebase with doc suggestions."""
    query = request.get("query", "")
    snippets = retrieve_relevant_snippets(str(engine.workspace_root), query, limit=3)

    doc_context = enhance_with_docs(str(engine.workspace_root), query)

    result = ""
    if doc_context:
        result += doc_context + "\n\n"

    if not snippets:
        engine._log_interaction(f"search {query}", "search", False)
        return f"{result}🔍 No code results for '{query}'" if result else f"🔍 No results for '{query}'"

    result += f"🔍 Found {len(snippets)} matches for '{query}':\n"
    for snip in snippets[:3]:
        path = snip.get("path", "unknown")[:50]
        result += f"  • {path}\n"

    engine._log_interaction(f"search {query}", "search", True, doc_context)
    return result


def _handle_research(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Research likely files and runtime constraints before proposing a change."""
    goal = str(request.get("goal") or request.get("raw_input") or "").strip()
    if not goal:
        goal = "general repository research"

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

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, path, reason in sorted(ranked_paths, key=lambda item: (-item[0], item[1])):
        if path in seen:
            continue
        seen.add(path)
        deduped.append((path, reason))
        if len(deduped) >= 5:
            break

    web_context = ""
    prefer_web = bool(request.get("prefer_web"))
    if prefer_web and web["enabled"]:
        web_context = enhance_with_docs(str(engine.workspace_root), goal)

    if not deduped:
        engine._log_interaction(goal, "research", False, web_context or None)
        return (
            "🔎 Research Summary\n"
            f"  • Goal: {goal}\n"
            "  • I couldn't identify a strong file target yet.\n"
            f"  • Web research: {web['summary']}\n"
            "  • Next step: try naming the surface, file, or user-visible area you want changed."
        )

    lines = [
        "🔎 Research Summary",
        f"  • Goal: {goal}",
        "  • Suggested workflow: research → identify files → edit/apply change",
        f"  • VS Code panel source: {awareness['known_surfaces']['vscode_panel']}",
        f"  • Server: {'up' if awareness['server']['reachable'] else 'down'} at {awareness['server']['url']}",
        f"  • Ollama: {'reachable' if awareness['ollama']['reachable'] else 'unreachable'} at {awareness['ollama']['url']}",
        f"  • Web research: {web['summary']}",
        "  • Likely files:",
    ]
    for path, reason in deduped:
        lines.append(f"    - {path} ({reason})")

    if web_context:
        lines.append("")
        lines.append(web_context)

    lines.append("")
    lines.append("  • Proposed next step: I can patch the likely files above directly.")
    engine._log_interaction(goal, "research", True, web_context or None)
    return "\n".join(lines)


def _handle_status(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Show project status with explicit lightweight/full validation modes."""
    validation_mode = str(request.get("validation_mode", "lightweight"))
    status: Any

    if validation_mode == "full":
        status = build_status_report(str(engine.workspace_root), mode="full")
        engine.context["status"] = status
    else:
        status = engine.context.get("status")
        if not status:
            status = build_status_report(str(engine.workspace_root), mode="lightweight")
            engine.context["status"] = status

    if not status:
        return "📊 Unable to load status"

    readiness = status.get("readiness", "unknown")
    benchmark = status.get("benchmark", {})
    score = benchmark.get("score", "N/A")

    return (
        "📊 Project Status:\n"
        f"  Validation Mode: {status.get('validation_mode', validation_mode)}\n"
        f"  Readiness: {readiness}\n"
        f"  Benchmark Score: {score}\n"
        f"  Roadmap: {status.get('roadmap', {}).get('percent', 'N/A')}% complete"
    )


def _handle_readiness(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Run self-improvement readiness canaries against the current engine/runtime."""
    report = run_engine_readiness_suite(engine)
    engine._log_interaction("readiness", "readiness", report.get("failed", 1) == 0)
    lines = [
        "🧪 Self-Improvement Readiness",
        f"  • Status: {report.get('status')}",
        f"  • Passed: {report.get('passed', 0)}/{report.get('total', 0)}",
        f"  • Routing generation: {report.get('routing_generation')}",
        f"  • Suite version: {report.get('readiness_suite_version')}",
        f"  • Server reachable: {report.get('server_reachable')}",
        f"  • Ollama reachable: {report.get('ollama_reachable')}",
        f"  • Web enabled: {report.get('web_enabled')}",
        f"  • VS Code panel: {report.get('known_vscode_panel')}",
    ]
    for item in report.get("results", [])[:5]:
        verdict = "✅" if item.get("passed") else "❌"
        lines.append(
            f"  • {verdict} {item.get('name')}: "
            f"{item.get('actual_action')} (expected {item.get('expected_action')})"
        )
        missing = item.get("missing_response_markers", [])
        if missing:
            lines.append(f"    missing markers: {', '.join(missing)}")
    return "\n".join(lines)


def _handle_remember(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Store a note in project memory."""
    memory = request.get("memory", "")
    key = memory.split(" ")[0] if memory else "note"
    value = " ".join(memory.split(" ")[1:]) if " " in memory else memory

    remember_note(str(engine.workspace_root), key=key, value=value)
    return f"✅ Remembered: {key} = {value}"


def _handle_browse(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Browse files and directories."""
    path = request.get("path", ".")
    target = engine.workspace_root / path if path != "." else engine.workspace_root

    try:
        target = target.resolve()
        target.relative_to(engine.workspace_root.resolve())
    except ValueError:
        return "❌ Access denied: outside workspace"
    except Exception:
        return f"❌ Invalid path: {path}"

    if not target.exists():
        return f"❌ Not found: {path}"

    if target.is_file():
        try:
            content = target.read_text(encoding="utf-8")
            lines = content.split("\n")
            if len(lines) <= 100:
                numbered = "\n".join(f"{i + 1:3d} | {line}" for i, line in enumerate(lines))
                return f"""📄 {target.name} ({len(lines)} lines):
```
{numbered[:2000]}
```"""

            preview = "\n".join(f"{i + 1:3d} | {line}" for i, line in enumerate(lines[:50]))
            return f"""📄 {target.name} ({len(lines)} lines) - Too long to display.
First 50 lines:
```
{preview}
```
Use 'show <file> 50-100' to see specific lines."""
        except Exception as exc:
            return f"❌ Can't read {path}: {str(exc)[:50]}"

    if target.is_dir():
        items: list[str] = []
        try:
            for item in sorted(target.iterdir()):
                if item.name.startswith("."):
                    continue

                rel_path = item.relative_to(engine.workspace_root)
                if item.is_dir():
                    items.append(f"📁 {rel_path}/")
                else:
                    size = item.stat().st_size
                    size_str = f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
                    items.append(f"📄 {rel_path} ({size_str})")
        except PermissionError:
            return f"❌ Permission denied: {path}"

        if not items:
            return f"📁 {path}/ (empty)"

        more = f"... and {len(items) - 30} more" if len(items) > 30 else ""
        return f"""📁 {path}/:
{chr(10).join(f"  {item}" for item in items[:30])}
{more}"""

    return f"❌ Unknown error browsing {path}"


def _handle_architecture(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Analyze codebase architecture and recommendations."""
    result = engine.architecture_analyzer.analyze("src")
    if "error" in result:
        engine._log_interaction("architecture", "architecture", False)
        return f"❌ {result['error']}"

    recommendations = result.get("recommendations", [])
    engine._log_interaction("architecture", "architecture", True)
    return f"""🏗️ Architecture Analysis
  • Python Files: {result.get('python_files', 0)}
  • Modules Indexed: {len(result.get('modules', []))}
  • Recommendations: {len(recommendations)}

{chr(10).join(f"  • {item}" for item in recommendations[:5])}"""


def _handle_git(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Provide git status/diff review and commit message suggestions."""
    query = request.get("query", "git status")

    if "diff" in query or "review" in query:
        summary = engine.git_integration.diff_summary()
        if "error" in summary:
            engine._log_interaction(query, "git", False)
            return f"❌ {summary['error']}"
        lines = ["🔎 Git Diff Summary:"]
        for item in summary.get("files", [])[:10]:
            lines.append(f"  • {item['path']}: +{item['added']} / -{item['removed']}")
        engine._log_interaction(query, "git", True)
        return "\n".join(lines) if len(lines) > 1 else "🔎 No unstaged changes found"

    if "commit message" in query:
        message = engine.git_integration.suggest_commit_message()
        if "error" in message:
            engine._log_interaction(query, "git", False)
            return f"❌ {message['error']}"
        engine._log_interaction(query, "git", True)
        return f"💬 Suggested commit message: {message.get('message')}"

    status = engine.git_integration.status_summary()
    if "error" in status:
        engine._log_interaction(query, "git", False)
        return f"❌ {status['error']}"
    engine._log_interaction(query, "git", True)
    return f"📦 Git status: {status.get('changed_files', 0)} changed file(s)"


def _handle_pr(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Generate a pull request draft from git changes."""
    result = engine.pr_generator.generate_pr()
    if "error" in result:
        engine._log_interaction("generate pr", "pr", False)
        return f"❌ {result['error']}"
    engine._log_interaction("generate pr", "pr", True)
    return f"✅ PR draft generated: {result.get('path')} ({result.get('changed_files')} files)"


def _handle_vscode(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Prepare VS Code project files and show workspace snapshot."""
    tasks = engine.vscode_integration.ensure_tasks()
    launch = engine.vscode_integration.ensure_launch()
    snapshot = engine.vscode_integration.workspace_snapshot()
    engine._log_interaction("vscode setup", "vscode", True)
    return (
        "🧩 VS Code integration ready\n"
        f"  • tasks: {tasks.get('status')} ({tasks.get('path')})\n"
        f"  • launch: {launch.get('status')} ({launch.get('path')})\n"
        f"  • python files: {snapshot.get('python_files')} | test files: {snapshot.get('test_files')}"
    )


def _handle_dashboard(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Show a compact dashboard summary from status and roadmap."""
    payload = engine.dashboard_builder.build()
    engine._log_interaction("dashboard", "dashboard", True)
    return (
        "📊 Dashboard Summary\n"
        f"  • Workspace: {payload.get('workspace')}\n"
        f"  • Readiness: {payload.get('readiness')}\n"
        f"  • Benchmark: {payload.get('benchmark_score')}\n"
        f"  • Roadmap: {payload.get('roadmap_percent')}% ({payload.get('roadmap_done')}/{payload.get('roadmap_total')})"
    )


def _handle_security_scan(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Scan source files for security vulnerabilities."""
    target = request.get("target", "src/")
    result = engine.security_scanner.scan_directory(target)
    engine._log_interaction(f"security scan {target}", "security_scan", True)
    fixes = engine.security_scanner.suggest_fixes(result.get("findings", []))
    lines = [
        "🔒 Security Scan Results",
        f"  • Files scanned: {result.get('scanned_files', 0)}",
        f"  • Total findings: {result.get('total_findings', 0)}",
        f"  • Critical: {result.get('critical', 0)}  High: {result.get('high', 0)}"
        f"  Medium: {result.get('medium', 0)}  Low: {result.get('low', 0)}",
    ]
    for fix in fixes[:5]:
        lines.append(f"  • {fix}")
    if not fixes:
        lines.append("  ✅ No issues found!")
    return "\n".join(lines)


def _handle_doc_generate(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Report undocumented code and generate docstring stubs."""
    target = request.get("target", "src/")
    result = engine.doc_generator.list_undocumented(target)
    engine._log_interaction(f"generate docs {target}", "doc_generate", True)
    lines = [
        "📝 Documentation Report",
        f"  • Missing docstrings: {result.get('total_missing_docstrings', 0)}",
        f"  • Files affected: {result.get('files_affected', 0)}",
    ]
    for file_report in result.get("details", [])[:3]:
        lines.append(f"  • {file_report['file']}: {file_report['undocumented']} missing")
        for ds in file_report.get("docstrings", [])[:2]:
            lines.append(f"    - {ds['type']} `{ds['name']}` (line {ds['line']})")
    return "\n".join(lines)


def _handle_api_generate(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Generate FastAPI route stubs from a Python file."""
    target = request.get("target", "src/")
    result = engine.api_generator.generate_from_file(target)
    engine._log_interaction(f"generate api {target}", "api_generate", True)
    if "error" in result:
        return f"⚠️ API Generator: {result['error']}"
    lines = [
        "⚡ API Routes Generated",
        f"  • File: {result.get('file', target)}",
        f"  • Routes: {result.get('route_count', 0)}",
    ]
    for route in result.get("routes", [])[:5]:
        lines.append(f"  • {route['method']} {route['endpoint']}  →  {route['name']}()")
    return "\n".join(lines)


def _handle_dep_resolve(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Analyse project dependencies for conflicts and upgrade paths."""
    result = engine.dependency_resolver.analyse()
    engine._log_interaction("resolve dependencies", "dep_resolve", True)
    if "error" in result:
        return f"⚠️ Dependency Resolver: {result['error']}"
    lines = [
        "📦 Dependency Analysis",
        f"  • File: {result.get('file', 'unknown')}",
        f"  • Packages: {result.get('total_packages', 0)}",
        f"  • Health: {result.get('health', 'UNKNOWN')}",
        f"  • Conflicts: {len(result.get('conflicts', []))}",
        f"  • Upgrade suggestions: {len(result.get('upgrade_suggestions', []))}",
    ]
    for up in result.get("upgrade_suggestions", [])[:4]:
        lines.append(f"  • {up['package']}: {up['current_spec']} → {up['suggested']}")
    return "\n".join(lines)


def _handle_cost_optimize(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Analyse LLM/API spending and surface savings suggestions."""
    result = engine.cost_optimizer.analyse()
    engine._log_interaction("optimize costs", "cost_optimize", True)
    lines = [
        "💸 Cost Optimisation Report",
        f"  • Status: {result.get('status')}",
        f"  • Total cost: ${result.get('total_cost_usd', 0):.6f}",
        f"  • Calls recorded: {result.get('total_calls', 0)}",
        f"  • Projected daily: ${result.get('projected_daily_cost_usd', 0):.4f}"
        f" (limit: ${result.get('budget_daily_limit_usd', 1.0):.2f})",
    ]
    for suggestion in result.get("suggestions", [])[:4]:
        lines.append(f"  • {suggestion}")
    return "\n".join(lines)


def _handle_team_kb(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Query team knowledge base for shared learnings."""
    query = request.get("query", "").strip()
    if query:
        result = engine.team_knowledge_base.search(query)
        title = f"🧠 Team Knowledge Base Search: '{query}'"
    else:
        result = engine.team_knowledge_base.recent(limit=5)
        title = "🧠 Team Knowledge Base Recent Entries"
    engine._log_interaction(f"team kb {query}".strip(), "team_kb", True)
    lines = [title, f"  • Matches: {result.get('count', 0)}"]
    for entry in result.get("entries", [])[:5]:
        lines.append(
            f"  • {entry.get('topic', 'general')} ({entry.get('author', 'unknown')}): {entry.get('note', '')}"
        )
    if result.get("count", 0) == 0:
        lines.append("  • No entries found yet. Add team notes to build shared memory.")
    return "\n".join(lines)


def _handle_audit_trail(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Return audit and compliance summary."""
    engine.audit_trail.log_action(action="audit_view", actor="chat", target="summary", allowed=True)
    summary = engine.audit_trail.compliance_summary()
    engine._log_interaction("audit trail", "audit_trail", True)
    lines = [
        "📜 Audit Trail Summary",
        f"  • Total events: {summary.get('total_events', 0)}",
        f"  • Allowed: {summary.get('allowed_events', 0)}",
        f"  • Denied: {summary.get('denied_events', 0)}",
        f"  • Status: {summary.get('status', 'OK')}",
    ]
    for item in summary.get("top_actions", [])[:3]:
        lines.append(f"  • {item.get('action')}: {item.get('count')} events")
    return "\n".join(lines)


def _handle_rbac(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Check role-based action permission."""
    role = request.get("role", "developer")
    permission = request.get("permission", "search")
    allowed = engine.role_permissions.is_allowed(permission, role=role)
    engine._log_interaction(f"rbac {role} {permission}", "rbac", True)
    verdict = "✅ Allowed" if allowed else "❌ Denied"
    return (
        "🛡️ Role-Based Permissions\n"
        f"  • Role: {role}\n"
        f"  • Action: {permission}\n"
        f"  • Decision: {verdict}"
    )


def _handle_team_analytics(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Generate team analytics snapshot."""
    report = engine.analytics_dashboard.generate()
    productivity = report.get("productivity", {})
    quality = report.get("quality", {})
    cost = report.get("cost", {})
    engine._log_interaction("team analytics", "team_analytics", True)
    return (
        "📊 Team Analytics Dashboard\n"
        f"  • Audit events: {productivity.get('audit_events', 0)}\n"
        f"  • Knowledge entries: {productivity.get('knowledge_entries', 0)}\n"
        f"  • Compliance rate: {quality.get('compliance_rate', 1.0)}\n"
        f"  • Denied actions: {quality.get('denied_actions', 0)}\n"
        f"  • Total cost: ${cost.get('total_cost_usd', 0.0):.6f}"
    )


def _handle_multi_language(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Summarize repository language mix and dominant language."""
    target = request.get("target", "src/")
    summary = engine.multi_language_support.language_summary(target)
    engine._log_interaction(f"language summary {target}", "multi_language", "error" not in summary)
    if "error" in summary:
        return f"⚠️ Multi-Language Support: {summary['error']}"

    lines = [
        "🌐 Multi-Language Summary",
        f"  • Target: {target}",
        f"  • Scanned files: {summary.get('scanned_files', 0)}",
        f"  • Dominant language: {summary.get('dominant_language', 'unknown')}",
    ]
    for item in summary.get("languages", [])[:6]:
        lines.append(f"  • {item.get('language')}: {item.get('files')} files")
    return "\n".join(lines)


def _handle_framework_expert(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Recommend framework expert mode and provide guidance."""
    task = request.get("task", "general")
    recommendation = engine.framework_experts.recommend_expert(task)
    framework = recommendation.get("framework", "fastapi")
    advice = engine.framework_experts.expert_advice(framework, task)
    engine._log_interaction(f"framework expert {task}", "framework_expert", "error" not in advice)
    if "error" in advice:
        return f"⚠️ Framework Expert: {advice['error']}"

    lines = [
        "🧠 Framework Expert Guidance",
        f"  • Framework: {framework}",
        f"  • Reason: {recommendation.get('reason', 'n/a')}",
        f"  • Focus: {advice.get('focus', 'general')}",
    ]
    for tip in advice.get("tips", [])[:3]:
        lines.append(f"  • {tip}")
    return "\n".join(lines)


def _handle_diagram_analyze(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Analyze architecture diagram text or file for flow understanding."""
    diagram = request.get("diagram", "").strip()
    file_path = request.get("file", "")
    if file_path:
        result = engine.architecture_diagram_understanding.analyze_file(file_path)
    else:
        result = engine.architecture_diagram_understanding.analyze_text(diagram)
    engine._log_interaction("analyze diagram", "diagram_analyze", "error" not in result)
    if "error" in result:
        return f"⚠️ Diagram Analyzer: {result['error']}"

    lines = [
        "🗺️ Architecture Diagram Analysis",
        f"  • Nodes: {result.get('node_count', 0)}",
        f"  • Connections: {result.get('edge_count', 0)}",
        f"  • Entry points: {', '.join(result.get('entry_points', [])) or 'none'}",
        f"  • Terminal nodes: {', '.join(result.get('terminal_nodes', [])) or 'none'}",
    ]
    for edge in result.get("edges", [])[:5]:
        lines.append(f"  • {edge['from']} → {edge['to']}")
    return "\n".join(lines)


def _handle_schema_analyze(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Analyze data schema DDL for structure and relationship insights."""
    schema = request.get("schema", "").strip()
    file_path = request.get("file", "")
    if file_path:
        result = engine.data_schema_analyzer.analyze_file(file_path)
    else:
        result = engine.data_schema_analyzer.analyze_sql(schema)
    engine._log_interaction("analyze schema", "schema_analyze", "error" not in result)
    if "error" in result:
        return f"⚠️ Schema Analyzer: {result['error']}"

    lines = [
        "🧱 Data Schema Analysis",
        f"  • Tables: {result.get('table_count', 0)}",
        f"  • Relationships: {result.get('relationship_count', 0)}",
    ]
    for table in result.get("tables", [])[:4]:
        lines.append(f"  • {table.get('table')}: {table.get('column_count', 0)} columns")
    for rec in result.get("recommendations", [])[:3]:
        lines.append(f"  • Suggestion: {rec}")
    return "\n".join(lines)


def _handle_diff_visualize(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Generate a compact visual summary of a diff."""
    diff_text = request.get("diff", "")
    diff_file = request.get("file", "")
    if diff_file:
        result = engine.diff_visualization.summarize_file(diff_file)
    else:
        result = engine.diff_visualization.summarize_diff(diff_text)
    engine._log_interaction("visualize diff", "diff_visualize", "error" not in result)
    if "error" in result:
        return f"⚠️ Diff Visualization: {result['error']}"

    lines = [
        "🧩 Diff Visualization",
        f"  • Files changed: {result.get('files_changed', 0)}",
        f"  • Added lines: {result.get('total_added', 0)}",
        f"  • Removed lines: {result.get('total_removed', 0)}",
    ]
    for item in result.get("files", [])[:5]:
        lines.append(
            f"  • {item.get('file')}: +{item.get('added', 0)} -{item.get('removed', 0)} {item.get('visual', '')}"
        )
    return "\n".join(lines)


def _handle_repo_summary(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Return an on-demand repository summary for user understanding prompts."""
    index = engine.context.get("index", [])
    if not index:
        index = build_file_index(str(engine.workspace_root))
        engine.context["index"] = index
    total_files = len(index)

    top_dirs: dict[str, int] = {}
    for entry in index:
        path = entry.get("path", "")
        head = path.split("/", 1)[0] if "/" in path else path
        if head:
            top_dirs[head] = top_dirs.get(head, 0) + 1

    ranked = sorted(top_dirs.items(), key=lambda item: item[1], reverse=True)[:6]
    engine._log_interaction("repo summary", "repo_summary", True)

    lines = [
        "📦 Repository Summary",
        f"  • Workspace: {engine.workspace_root.name}",
        f"  • Indexed files: {total_files}",
        "  • Top folders:",
    ]
    for folder, count in ranked:
        lines.append(f"    - {folder}: {count} files")

    lines.append("  • Core entrypoints: src/main.py, src/server.py, src/tools/chat_engine.py")
    return "\n".join(lines)


REPO_HANDLERS = {
    "_handle_research": _handle_research,
    "_handle_search": _handle_search,
    "_handle_readiness": _handle_readiness,
    "_handle_status": _handle_status,
    "_handle_remember": _handle_remember,
    "_handle_browse": _handle_browse,
    "_handle_architecture": _handle_architecture,
    "_handle_git": _handle_git,
    "_handle_pr": _handle_pr,
    "_handle_vscode": _handle_vscode,
    "_handle_dashboard": _handle_dashboard,
    "_handle_security_scan": _handle_security_scan,
    "_handle_doc_generate": _handle_doc_generate,
    "_handle_api_generate": _handle_api_generate,
    "_handle_dep_resolve": _handle_dep_resolve,
    "_handle_cost_optimize": _handle_cost_optimize,
    "_handle_team_kb": _handle_team_kb,
    "_handle_audit_trail": _handle_audit_trail,
    "_handle_rbac": _handle_rbac,
    "_handle_team_analytics": _handle_team_analytics,
    "_handle_multi_language": _handle_multi_language,
    "_handle_framework_expert": _handle_framework_expert,
    "_handle_diagram_analyze": _handle_diagram_analyze,
    "_handle_schema_analyze": _handle_schema_analyze,
    "_handle_diff_visualize": _handle_diff_visualize,
    "_handle_repo_summary": _handle_repo_summary,
}
