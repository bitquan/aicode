"""Interactive chat interface with shared typed routing and thin coordination."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Generator, Optional
from urllib.error import URLError
from urllib.request import urlopen

from src.agents.coding_agent import CodingAgent
from src.config.capabilities import load_capabilities
from src.tools.agent_memory import AgentMemoryStore
from src.tools.agent_router import AgentRouter
from src.tools.analytics_dashboard import AnalyticsDashboard
from src.tools.api_generator import APIGenerator
from src.tools.architecture_analyzer import ArchitectureAnalyzer
from src.tools.architecture_diagram_understanding import ArchitectureDiagramUnderstanding
from src.tools.audit_trail import AuditTrail
from src.tools.code_reviewer import CodeReviewer
from src.tools.commanding import (
    ACTION_HANDLER_METHODS,
    ActionDispatcher,
    ActionRequest,
    ActionResponse,
    ChatRequestParser,
)
from src.tools.commanding.handlers import ALL_HANDLER_GROUPS
from src.tools.cost_optimizer import CostOptimizer
from src.tools.coverage_analyzer import TestCoverageAnalyzer
from src.tools.custom_llm_support import CustomLLMSupport
from src.tools.dashboard import DashboardBuilder
from src.tools.data_schema_analyzer import DataSchemaAnalyzer
from src.tools.debugger import PythonDebugger
from src.tools.dependency_resolver import DependencyResolver
from src.tools.diff_visualization import DiffVisualization
from src.tools.doc_fetcher import DocFetcher
from src.tools.doc_generator import DocGenerator
from src.tools.framework_experts import FrameworkExperts
from src.tools.git_integration import GitIntegration
from src.tools.knowledge_transfer import KnowledgeTransfer
from src.tools.learned_preferences import get_preferences, retrieve_preferences
from src.tools.learning_events import read_prompt_events
from src.tools.multi_agent import MultiAgentCoordinator
from src.tools.multi_language_support import MultiLanguageSupport
from src.tools.pr_generator import PRGenerator
from src.tools.profiler import CodeProfiler
from src.tools.project_memory import get_notes
from src.tools.prompt_lab import PromptLab
from src.tools.repo_index import build_file_index
from src.tools.role_permissions import RolePermissions
from src.tools.security_scanner import SecurityScanner
from src.tools.self_builder import SelfBuilder
from src.tools.self_improve import build_self_improvement_status_snapshot, run_self_improvement_cycles
from src.tools.status_report import build_status_report
from src.tools.team_knowledge_base import TeamKnowledgeBase
from src.tools.tool_builder import ToolBuilder
from src.tools.vscode_integration import VSCodeIntegration


logger = logging.getLogger(__name__)
LOW_CONFIDENCE_RESEARCH_THRESHOLD = 0.66


class MarkdownRenderer:
    """Render markdown in terminal with colors and formatting."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"

    @classmethod
    def render(cls, text: str) -> str:
        """Render markdown to terminal output."""
        lines = text.split("\n")
        rendered = []
        in_code = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                if in_code:
                    rendered.append(f"\n{cls.DIM}─────────────────────{cls.RESET}")
                else:
                    rendered.append(f"{cls.DIM}─────────────────────{cls.RESET}\n")
                continue

            if in_code:
                rendered.append(f"{cls.CYAN}{line}{cls.RESET}")
            elif line.startswith("# "):
                rendered.append(f"{cls.BOLD}{cls.MAGENTA}{line[2:]}{cls.RESET}")
            elif line.startswith("## "):
                rendered.append(f"{cls.BOLD}{cls.BLUE}{line[3:]}{cls.RESET}")
            elif line.startswith("### "):
                rendered.append(f"{cls.BOLD}{line[4:]}{cls.RESET}")
            elif "**" in line:
                rendered.append(f"{cls.BOLD}{line.replace('**', '')}{cls.RESET}")
            elif line.startswith("- "):
                rendered.append(f"{cls.GREEN}•{cls.RESET} {line[2:]}")
            elif line.startswith("  - "):
                rendered.append(f"{cls.GREEN}  ◦{cls.RESET} {line[4:]}")
            elif "✅" in line or "✓" in line:
                rendered.append(f"{cls.GREEN}{line}{cls.RESET}")
            elif "⚠️" in line or "❌" in line:
                rendered.append(f"{cls.YELLOW}{line}{cls.RESET}")
            else:
                rendered.append(line)

        return "\n".join(rendered)

    @classmethod
    def stream(cls, chunks: Generator[str, None, None]) -> None:
        """Stream rendered output chunk by chunk."""
        buffer = ""
        for chunk in chunks:
            buffer += chunk
            if "\n" in buffer:
                lines = buffer.split("\n")
                for line in lines[:-1]:
                    print(cls.render(line), flush=True)
                buffer = lines[-1]
        if buffer:
            print(cls.render(buffer), flush=True)


class ChatEngine:
    """Conversational interface that understands coding requests."""

    def __init__(self, workspace_root: str = ".", load_context: bool = True):
        self.workspace_root = Path(workspace_root).resolve()
        self.agent = CodingAgent()
        self.capabilities = load_capabilities()
        self.context: dict[str, Any] = {}
        self.doc_fetcher = DocFetcher(str(self.workspace_root))
        self.self_builder = SelfBuilder(str(self.workspace_root))
        self.code_reviewer = CodeReviewer(str(self.workspace_root))
        self.debugger = PythonDebugger(str(self.workspace_root))
        self.profiler = CodeProfiler(str(self.workspace_root))
        self.coverage_analyzer = TestCoverageAnalyzer(str(self.workspace_root))
        self.knowledge_transfer = KnowledgeTransfer(str(self.workspace_root))
        self.prompt_lab = PromptLab(str(self.workspace_root))
        self.tool_builder = ToolBuilder(str(self.workspace_root))
        self.architecture_analyzer = ArchitectureAnalyzer(str(self.workspace_root))
        self.git_integration = GitIntegration(str(self.workspace_root))
        self.pr_generator = PRGenerator(str(self.workspace_root))
        self.vscode_integration = VSCodeIntegration(str(self.workspace_root))
        self.dashboard_builder = DashboardBuilder(str(self.workspace_root))
        self.agent_memory = AgentMemoryStore(str(self.workspace_root))
        self.agent_router = AgentRouter()
        self.multi_agent = MultiAgentCoordinator(str(self.workspace_root))
        self.security_scanner = SecurityScanner(str(self.workspace_root))
        self.doc_generator = DocGenerator(str(self.workspace_root))
        self.api_generator = APIGenerator(str(self.workspace_root))
        self.dependency_resolver = DependencyResolver(str(self.workspace_root))
        self.cost_optimizer = CostOptimizer(str(self.workspace_root))
        self.team_knowledge_base = TeamKnowledgeBase(str(self.workspace_root))
        self.audit_trail = AuditTrail(str(self.workspace_root))
        self.role_permissions = RolePermissions(str(self.workspace_root))
        self.custom_llm_support = CustomLLMSupport(str(self.workspace_root))
        self.analytics_dashboard = AnalyticsDashboard(str(self.workspace_root))
        self.multi_language_support = MultiLanguageSupport(str(self.workspace_root))
        self.framework_experts = FrameworkExperts(str(self.workspace_root))
        self.architecture_diagram_understanding = ArchitectureDiagramUnderstanding(str(self.workspace_root))
        self.data_schema_analyzer = DataSchemaAnalyzer(str(self.workspace_root))
        self.diff_visualization = DiffVisualization(str(self.workspace_root))
        self.interaction_log: list[dict[str, Any]] = []
        self._last_applied_preferences: list[dict[str, str]] = []
        self.request_parser = ChatRequestParser(self._looks_like_code_request)
        self.dispatcher = ActionDispatcher()
        if load_context:
            self._load_context()

    def _load_context(self) -> None:
        """Load repo context for smarter responses."""
        try:
            self.context["index"] = build_file_index(str(self.workspace_root))
            self.context["status"] = build_status_report(str(self.workspace_root), mode="lightweight")

            packages = self.doc_fetcher.extract_requirements(str(self.workspace_root / "pyproject.toml"))
            if not packages:
                packages = self.doc_fetcher.extract_requirements(str(self.workspace_root / "requirements.txt"))
            if packages:
                self.doc_fetcher.index_library(packages)
                self.context["packages"] = packages

            self.context["knowledge_base"] = self.self_builder.export_knowledge_base()
        except Exception as exc:
            logger.warning(
                "event=chat_engine_load_context_failed workspace_root=%s error=%s",
                self.workspace_root,
                exc,
            )

    def _log_interaction(
        self,
        query: str,
        action: str,
        success: bool,
        doc_context: Optional[str] = None,
    ) -> None:
        """Log interaction for learning and improvement."""
        self.interaction_log.append(
            {
                "query": query,
                "action": action,
                "success": success,
                "doc_context": doc_context,
                "timestamp": str(Path.home() / ".dev_timestamp"),
            }
        )

    def _looks_like_code_request(self, lower: str) -> bool:
        """Heuristic check for direct coding intent when prompt is otherwise unmatched."""
        code_signals = (
            "function",
            "class",
            "method",
            "implement",
            "refactor",
            "bug",
            "error",
            "exception",
            "code",
            "python",
            "javascript",
            "typescript",
            "sql",
            "api",
            "endpoint",
            "unit test",
            "test case",
        )
        return any(signal in lower for signal in code_signals)

    def _server_base_url(self) -> str:
        host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = os.getenv("PORT", "8005").strip() or "8005"
        return f"http://{host}:{port}"

    @staticmethod
    def _json_probe(url: str, timeout_seconds: float = 0.35) -> dict[str, Any]:
        try:
            with urlopen(url, timeout=timeout_seconds) as response:
                payload = response.read().decode("utf-8")
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else {}
        except (OSError, ValueError, URLError):
            return {}

    def web_policy(self) -> dict[str, Any]:
        policy = self.capabilities.get("web_policy", {})
        if not isinstance(policy, dict):
            policy = {}
        enabled = bool(policy.get("enabled", self.capabilities.get("web_fetch", False)))
        mode = str(policy.get("mode", "optional"))
        requires_explicit_request = bool(policy.get("requires_explicit_request", True))
        provider = str(policy.get("provider", "doc_fetcher"))
        return {
            "enabled": enabled,
            "mode": mode,
            "requires_explicit_request": requires_explicit_request,
            "provider": provider,
            "summary": (
                f"{'enabled' if enabled else 'disabled'}"
                f" ({mode}; {'explicit requests only' if requires_explicit_request else 'available by default'})"
            ),
        }

    def get_self_awareness_snapshot(self) -> dict[str, Any]:
        """Return live runtime and capability awareness for research/help flows."""
        server_url = self._server_base_url()
        server_health = self._json_probe(f"{server_url}/healthz")

        ollama_url = str(
            server_health.get("base_url")
            or getattr(self.agent, "base_url", "http://127.0.0.1:11434")
        ).rstrip("/")
        ollama_payload = server_health.get("ollama")
        if isinstance(ollama_payload, dict):
            ollama = {
                "reachable": bool(ollama_payload.get("reachable", False)),
                "detail": str(ollama_payload.get("detail", "unknown")),
                "url": ollama_url,
                "model_available": bool(ollama_payload.get("model_available", False)),
            }
        else:
            tags_payload = self._json_probe(f"{ollama_url}/api/tags")
            ollama = {
                "reachable": bool(tags_payload),
                "detail": "reachable" if tags_payload else "unreachable",
                "url": ollama_url,
                "model_available": isinstance(tags_payload.get("models"), list),
            }

        known_surfaces = {
            "vscode_panel": "vscode-extension/src/extension.ts",
            "extension_manifest": "vscode-extension/package.json",
            "server": "src/server.py",
            "request_parser": "src/tools/commanding/request_parser.py",
            "dispatcher": "src/tools/commanding/dispatcher.py",
            "app_service": "src/app_service.py",
        }
        self_improvement = build_self_improvement_status_snapshot(str(self.workspace_root))
        recent_events = read_prompt_events(str(self.workspace_root), limit=120)
        event_count = len(recent_events)
        avg_confidence = round(
            sum(float(item.get("confidence", 0.0) or 0.0) for item in recent_events) / event_count,
            3,
        ) if event_count else 0.0
        research_trigger_count = sum(1 for item in recent_events if bool(item.get("needs_external_research", False)))
        recent_decision_metrics = {
            "events_considered": event_count,
            "avg_confidence": avg_confidence,
            "research_trigger_count": research_trigger_count,
            "research_trigger_rate": round(research_trigger_count / event_count, 3) if event_count else 0.0,
        }

        return {
            "workspace_root": str(self.workspace_root),
            "known_surfaces": known_surfaces,
            "editable_surfaces": sorted(known_surfaces.values()),
            "server": {
                "reachable": bool(server_health),
                "status": str(server_health.get("status", "unreachable")),
                "url": server_url,
                "workspace_root": str(server_health.get("workspace_root", self.workspace_root)),
            },
            "ollama": ollama,
            "web": self.web_policy(),
            "confidence_policy": {
                "low_confidence_research_threshold": LOW_CONFIDENCE_RESEARCH_THRESHOLD,
                "reroute_actions": ["clarify", "generate"],
            },
            "recent_decision_metrics": recent_decision_metrics,
            "self_improvement": self_improvement,
            "commands": sorted(action for action in ACTION_HANDLER_METHODS if action != "clarify"),
        }

    def parse_request_model(self, user_input: str) -> ActionRequest:
        """Parse natural-language input into a typed action request."""
        lower = user_input.strip().lower()
        affirmative_prompts = {"yes", "yes do that", "do that", "sounds good", "ok do that", "okay do that"}
        last_response_action = str(self.context.get("last_response_action", ""))
        last_response_text = str(self.context.get("last_response_text", ""))

        if lower in affirmative_prompts:
            if last_response_action == "help_summary" and "use this response style by default" in last_response_text.lower():
                return ActionRequest(
                    action="user_learn",
                    confidence=0.96,
                    raw_input=user_input,
                    params={
                        "lesson": "Prefer concise, human, next-step-oriented responses by default.",
                    },
                )

        return self.request_parser.parse(user_input)

    def parse_request(self, user_input: str) -> dict[str, Any]:
        """Backward-compatible dict API for existing callers and tests."""
        return self.parse_request_model(user_input).to_legacy_dict()

    @staticmethod
    def _looks_freshness_sensitive_query(text: str) -> bool:
        lower = text.lower()
        return any(
            marker in lower
            for marker in (
                "latest",
                "newest",
                "updated",
                "current version",
                "official docs",
                "release notes",
            )
        )

    def _should_reroute_to_research(self, request: ActionRequest) -> tuple[bool, str | None]:
        if request.action == "research":
            return False, None

        if request.action in {"help_summary", "self_aware_summary", "status", "repo_summary"}:
            return False, None

        policy = self.web_policy()
        if not policy.get("enabled", False):
            return False, None

        goal_text = request.raw_input or str(request.get("instruction", "")).strip()
        if not goal_text:
            return False, None

        confidence_value = float(request.confidence or 0.0)
        low_confidence = confidence_value > 0.0 and confidence_value < LOW_CONFIDENCE_RESEARCH_THRESHOLD
        prefer_web = bool(request.get("prefer_web", False))
        freshness_sensitive = self._looks_freshness_sensitive_query(goal_text)
        explicit_only = bool(policy.get("requires_explicit_request", True))

        if prefer_web and request.action in {"clarify", "generate", "search", "repo_summary"}:
            return True, "explicit_web_preference"

        if freshness_sensitive and request.action in {"clarify", "generate", "search", "repo_summary"}:
            return True, "freshness_sensitive_query"

        if low_confidence and request.action in {"clarify", "generate"}:
            if explicit_only and not (prefer_web or freshness_sensitive):
                return True, "low_confidence_unknown"
            return True, "low_confidence_unknown"

        return False, None

    def execute_request(self, request: ActionRequest | dict[str, Any]) -> ActionResponse:
        """Execute a typed action request."""
        typed_request = request if isinstance(request, ActionRequest) else ActionRequest.from_mapping(request)
        should_reroute, reason = self._should_reroute_to_research(typed_request)

        if should_reroute:
            research_request = ActionRequest(
                action="research",
                confidence=max(float(typed_request.confidence or 0.0), 0.78),
                raw_input=typed_request.raw_input,
                params={
                    "goal": typed_request.raw_input or str(typed_request.get("instruction", "")).strip(),
                    "prefer_web": True,
                    "research_trigger_reason": reason,
                    "original_action": typed_request.action,
                },
            )
            response = self.dispatcher.dispatch(self, research_request)
            response.data.setdefault("needs_external_research", True)
            response.data.setdefault("research_trigger_reason", reason)
            response.data.setdefault("route_attempts", [typed_request.action, "research"])
            self.context["last_response_action"] = response.action
            self.context["last_response_text"] = response.text
            return response

        response = self.dispatcher.dispatch(self, typed_request)
        response.data.setdefault("needs_external_research", False)
        response.data.setdefault("research_trigger_reason", None)
        response.data.setdefault("route_attempts", [typed_request.action])
        self.context["last_response_action"] = response.action
        self.context["last_response_text"] = response.text
        return response

    def execute(self, request: dict[str, Any]) -> str:
        """Backward-compatible string API for existing callers and tests."""
        return self.execute_request(request).text

    def _apply_user_preferences(self, instruction: str, request_intent: str) -> str:
        """Append learned user preferences to execution prompts when available."""
        self._last_applied_preferences = []
        has_structured_preferences = len(get_preferences(str(self.workspace_root), active_only=False)) > 0
        retrieved = retrieve_preferences(
            workspace_root=str(self.workspace_root),
            request_intent=request_intent,
            top_k=3,
        )
        if retrieved:
            self._last_applied_preferences = [
                {
                    "preference_id": str(item.get("preference_id", "")),
                    "statement": str(item.get("statement", "")),
                    "retrieval_reason": str(item.get("retrieval_reason", "")),
                }
                for item in retrieved
            ]
            lines = [f"- {item['statement']} ({item['retrieval_reason']})" for item in retrieved]
            preference_block = "\n\nUser Preferences:\n" + "\n".join(lines)
            return f"{instruction}{preference_block}" if instruction else preference_block.strip()

        if has_structured_preferences:
            return instruction

        notes = get_notes(str(self.workspace_root), key="lesson", limit=10)
        lessons: list[str] = []
        seen: set[str] = set()

        for row in reversed(notes):
            value = str(row.get("value", "")).strip()
            if value and value not in seen:
                seen.add(value)
                lessons.append(value)

        if len(lessons) < 3:
            kb_recent = self.team_knowledge_base.recent(limit=10).get("entries", [])
            for entry in kb_recent:
                if entry.get("topic") != "user_input":
                    continue
                value = str(entry.get("note", "")).strip()
                if value and value not in seen:
                    seen.add(value)
                    lessons.append(value)
                if len(lessons) >= 3:
                    break

        if not lessons:
            return instruction

        self._last_applied_preferences = [
            {
                "preference_id": "legacy_note",
                "statement": item,
                "retrieval_reason": "legacy lesson fallback",
            }
            for item in lessons[:3]
        ]

        preference_block = "\n\nUser Preferences:\n" + "\n".join(f"- {item}" for item in lessons[:3])
        return f"{instruction}{preference_block}" if instruction else preference_block.strip()

    def get_last_applied_preferences(self) -> list[dict[str, str]]:
        """Return preferences applied to the most recent generate/autofix call."""
        return list(self._last_applied_preferences)

    def prefers_conversational_responses(self, request_intent: str = "help_summary") -> bool:
        """Return whether learned preferences indicate concise, human-style replies."""
        candidate_texts: list[str] = []

        for item in retrieve_preferences(
            workspace_root=str(self.workspace_root),
            request_intent=request_intent,
            top_k=5,
        ):
            candidate_texts.append(str(item.get("statement", "")))

        if not candidate_texts:
            for row in get_notes(str(self.workspace_root), key="lesson", limit=10):
                candidate_texts.append(str(row.get("value", "")))

        markers = (
            "concise",
            "human",
            "shorter",
            "clearer",
            "next-step",
            "next step",
            "talk like a human",
        )
        for text in candidate_texts:
            lower = text.lower().strip()
            if lower and any(marker in lower for marker in markers):
                return True
        return False

    def _infer_preference_category(self, lesson: str) -> str:
        """Infer a baseline preference category from freeform lesson text."""
        lower = lesson.lower()
        if any(token in lower for token in ("style", "format", "naming", "readable")):
            return "style"
        if any(token in lower for token in ("test", "coverage", "pytest")):
            return "testing"
        if any(token in lower for token in ("safe", "security", "sanitize", "validate")):
            return "safety"
        if any(token in lower for token in ("tool", "lint", "build", "ci")):
            return "tooling"
        if any(token in lower for token in ("output", "response", "formatting", "concise")):
            return "output_format"
        return "workflow"

    def _run_self_improvement_cycles(
        self,
        *,
        cycles: int,
        target_score: float,
        report_timeout_seconds: float,
    ) -> dict[str, Any]:
        """Compatibility seam for tests that patch the module-level self-improve entrypoint."""
        return run_self_improvement_cycles(
            str(self.workspace_root),
            cycles=cycles,
            target_score=target_score,
            report_timeout_seconds=report_timeout_seconds,
        )


for handler_group in ALL_HANDLER_GROUPS:
    for handler_name, handler in handler_group.items():
        setattr(ChatEngine, handler_name, handler)


def run_chat_session(workspace_root: str = ".") -> None:
    """Run interactive chat session."""
    engine = ChatEngine(workspace_root)

    print("🤖 aicode Chat - Talk naturally about your code")
    print("Type 'help' for examples, 'quit' to exit\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if user_input.lower() == "help":
                print(
                    """
Examples:
  > write a function that reverses strings
  > add type hints to src/main.py
  > fix src/utils.py
  > search for get_user_by_id
  > status
  > remember lesson always test edge cases
                """
                )
                continue

            request = engine.parse_request(user_input)
            response = engine.execute(request)
            print(f"🤖 {response}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as exc:  # pragma: no cover - interactive fallback
            print(f"⚠️ Error: {str(exc)}\n")
