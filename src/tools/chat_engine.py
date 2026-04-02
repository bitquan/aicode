"""Interactive chat interface with shared typed routing and thin coordination."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator, Optional

from src.agents.coding_agent import CodingAgent
from src.tools.agent_memory import AgentMemoryStore
from src.tools.agent_router import AgentRouter
from src.tools.analytics_dashboard import AnalyticsDashboard
from src.tools.api_generator import APIGenerator
from src.tools.architecture_analyzer import ArchitectureAnalyzer
from src.tools.architecture_diagram_understanding import ArchitectureDiagramUnderstanding
from src.tools.audit_trail import AuditTrail
from src.tools.code_reviewer import CodeReviewer
from src.tools.commanding import ActionDispatcher, ActionRequest, ActionResponse, ChatRequestParser
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
from src.tools.self_improve import run_self_improvement_cycles
from src.tools.status_report import build_status_report
from src.tools.team_knowledge_base import TeamKnowledgeBase
from src.tools.tool_builder import ToolBuilder
from src.tools.vscode_integration import VSCodeIntegration


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
        except Exception:
            pass

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

    def parse_request_model(self, user_input: str) -> ActionRequest:
        """Parse natural-language input into a typed action request."""
        return self.request_parser.parse(user_input)

    def parse_request(self, user_input: str) -> dict[str, Any]:
        """Backward-compatible dict API for existing callers and tests."""
        return self.parse_request_model(user_input).to_legacy_dict()

    def execute_request(self, request: ActionRequest | dict[str, Any]) -> ActionResponse:
        """Execute a typed action request."""
        typed_request = request if isinstance(request, ActionRequest) else ActionRequest.from_mapping(request)
        return self.dispatcher.dispatch(self, typed_request)

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
