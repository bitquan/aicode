"""Shared action dispatcher and registry for app command handlers."""

from __future__ import annotations

from typing import Any

from src.tools.commanding.models import ActionRequest, ActionResponse

UNKNOWN_ACTION_MESSAGE = (
    "❓ I didn't understand that. Try: 'write <code>', 'fix <file>', 'review <file>', "
    "'debug <file>', 'profile <file>', 'coverage <file>', 'export knowledge', "
    "'import knowledge <file>', 'prompt lab', 'build tool <name>', 'architecture', "
    "'analyze diagram <text>', 'analyze schema', 'visualize diff', 'git status', "
    "'generate pr', 'vscode setup', 'dashboard', 'collaborate <task>', "
    "'route task <task>', 'agent memory <topic>', 'security scan <dir>', "
    "'generate docs <file>', 'generate api <file>', 'resolve dependencies', "
    "'optimize costs', 'team kb <query>', 'audit trail', 'rbac', 'model route <task>', "
    "'team analytics', 'language summary <path>', 'framework expert <task>', "
    "'search <query>', 'browse <path>', 'learn', 'self build', or 'status'"
)

ACTION_HANDLER_METHODS = {
    "generate": "_handle_generate",
    "edit": "_handle_edit",
    "autofix": "_handle_autofix",
    "search": "_handle_search",
    "status": "_handle_status",
    "remember": "_handle_remember",
    "user_learn": "_handle_user_learn",
    "user_correct": "_handle_user_correct",
    "clear_preferences": "_handle_clear_preferences",
    "browse": "_handle_browse",
    "learn": "_handle_learn",
    "self_build": "_handle_self_build",
    "review": "_handle_review",
    "debug": "_handle_debug",
    "profile": "_handle_profile",
    "coverage": "_handle_coverage",
    "knowledge_transfer": "_handle_knowledge_transfer",
    "prompt_lab": "_handle_prompt_lab",
    "tool_builder": "_handle_tool_builder",
    "architecture": "_handle_architecture",
    "git": "_handle_git",
    "pr": "_handle_pr",
    "vscode": "_handle_vscode",
    "dashboard": "_handle_dashboard",
    "learning_metrics": "_handle_learning_metrics",
    "multi_agent": "_handle_multi_agent",
    "agent_route": "_handle_agent_route",
    "agent_memory": "_handle_agent_memory",
    "security_scan": "_handle_security_scan",
    "doc_generate": "_handle_doc_generate",
    "api_generate": "_handle_api_generate",
    "dep_resolve": "_handle_dep_resolve",
    "cost_optimize": "_handle_cost_optimize",
    "team_kb": "_handle_team_kb",
    "audit_trail": "_handle_audit_trail",
    "rbac": "_handle_rbac",
    "custom_llm": "_handle_custom_llm",
    "team_analytics": "_handle_team_analytics",
    "multi_language": "_handle_multi_language",
    "framework_expert": "_handle_framework_expert",
    "diagram_analyze": "_handle_diagram_analyze",
    "schema_analyze": "_handle_schema_analyze",
    "diff_visualize": "_handle_diff_visualize",
    "help_summary": "_handle_help_summary",
    "repo_summary": "_handle_repo_summary",
    "clarify": "_handle_clarify",
}


class ActionDispatcher:
    """Dispatch typed requests to the registered ChatEngine handlers."""

    def dispatch(self, engine: Any, request: ActionRequest) -> ActionResponse:
        method_name = ACTION_HANDLER_METHODS.get(request.action)
        if method_name is None:
            return ActionResponse.from_text(
                action=request.action or "unknown",
                text=UNKNOWN_ACTION_MESSAGE,
                confidence=request.confidence,
            )

        try:
            handler = getattr(engine, method_name)
            text = handler(request.to_legacy_dict())
        except Exception as exc:  # pragma: no cover - defensive guard
            return ActionResponse.from_text(
                action=request.action,
                text=f"⚠️ Error: {str(exc)[:100]}",
                confidence=request.confidence,
            )

        return ActionResponse.from_text(
            action=request.action,
            text=text,
            confidence=request.confidence,
        )
