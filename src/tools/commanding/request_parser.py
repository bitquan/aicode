"""Natural-language command parser shared by chat, CLI, and API surfaces."""

from __future__ import annotations

from typing import Any, Callable

from src.tools.commanding.models import ActionRequest
from src.tools.prompt_taxonomy import classify_prompt_type


class ChatRequestParser:
    """Parse natural-language prompts into typed action requests."""

    def __init__(self, looks_like_code_request: Callable[[str], bool]):
        self._looks_like_code_request = looks_like_code_request

    def parse(self, user_input: str) -> ActionRequest:
        lower = user_input.lower().strip()

        def build(action: str, confidence: float, **params: Any) -> ActionRequest:
            return ActionRequest(
                action=action,
                confidence=confidence,
                raw_input=user_input,
                params=params,
            )

        if any(lower.startswith(cmd) for cmd in ["browse ", "ls ", "show ", "open "]):
            parts = lower.split(" ", 1)
            path = parts[1] if len(parts) > 1 else "."
            return build("browse", 0.95, path=path)

        if lower.startswith("add "):
            parts = lower.split(" to ")
            if len(parts) == 2:
                feature = parts[0].replace("add ", "").strip()
                target = parts[1].strip()
                return build(
                    "edit",
                    0.85,
                    target=target,
                    instruction=f"Add {feature}",
                )

        if lower.startswith("fix "):
            target = lower.replace("fix ", "").strip()
            return build(
                "autofix",
                0.9,
                target=target,
                instruction=f"Fix issues in {target}",
                stream=True,
            )

        if lower.startswith("write "):
            desc = lower.replace("write ", "").strip()
            return build("generate", 0.85, instruction=desc, stream=True)

        if lower.startswith(("search ", "find ", "where ")):
            query = lower.split(" ", 1)[1] if " " in lower else ""
            return build("search", 0.8, query=query)

        prompt_class = classify_prompt_type(user_input)
        if prompt_class.get("intent") == "repo_summary":
            return build("repo_summary", 0.95)

        if lower.startswith(("learn:", "teach:", "remember this", "note:")):
            lesson = user_input
            for prefix in ("learn:", "teach:", "remember this", "note:"):
                if lower.startswith(prefix):
                    lesson = user_input[len(prefix):].strip()
                    break
            return build("user_learn", 0.95, lesson=lesson)

        if lower.startswith(
            (
                "correct:",
                "correction:",
                "replace preference:",
                "disable preference",
                "strengthen preference",
            )
        ):
            correction_type = "replace"
            correction_text = user_input

            if lower.startswith(("correct:", "correction:", "replace preference:")):
                for prefix in ("correct:", "correction:", "replace preference:"):
                    if lower.startswith(prefix):
                        correction_text = user_input[len(prefix):].strip()
                        break
            elif lower.startswith("disable preference"):
                correction_type = "disable"
                correction_text = user_input.replace("disable preference", "", 1).strip()
            elif lower.startswith("strengthen preference"):
                correction_type = "strengthen"
                correction_text = user_input.replace("strengthen preference", "", 1).strip()

            return build(
                "user_correct",
                0.95,
                correction_type=correction_type,
                correction_text=correction_text,
            )

        if lower.startswith(
            ("clear learned preference", "clear learned preferences", "clear preferences")
        ):
            return build("clear_preferences", 0.95)

        if any(
            phrase in lower
            for phrase in (
                "self build",
                "self-build",
                "build itself",
                "improve itself",
                "build it self",
                "help build itself",
            )
        ):
            cycles = 1
            for token in user_input.split():
                if token.isdigit():
                    cycles = max(1, min(int(token), 5))
                    break
            return build("self_build", 0.95, cycles=cycles)

        if lower.startswith(("git status", "git diff", "git review", "commit message")):
            return build("git", 0.9, query=lower)

        if any(
            phrase in lower
            for phrase in (
                "full status",
                "status full",
                "run validation",
                "full validation",
                "validate repo",
                "validate project",
            )
        ):
            return build("status", 0.95, validation_mode="full")

        if any(word in lower for word in ["status", "score", "how are we", "progress", "health"]):
            return build("status", 0.95, validation_mode="lightweight")

        if lower.startswith(("remember ", "note ")):
            rest = lower.split(" ", 1)[1]
            return build("remember", 0.8, memory=rest)

        if (
            any(
                word in lower
                for word in ["learn", "improve myself", "self-improve", "self improve", "build myself"]
            )
            and not lower.startswith(("learning metrics", "baseline metrics", "metrics harness"))
        ):
            return build("learn", 0.9)

        if lower.startswith(("review ", "check ", "audit ")) and not lower.startswith(
            ("audit trail", "audit log", "check role")
        ):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return build("review", 0.9, target=target)

        if lower.startswith(("debug ", "trace ", "step ")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/main.py"
            return build("debug", 0.9, target=target)

        if lower.startswith(("optimize cost", "cost optimize", "cost report", "spending")):
            return build("cost_optimize", 0.9)

        if lower.startswith(("profile ", "optimize ")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return build("profile", 0.9, target=target)

        if lower.startswith(("coverage ", "test coverage")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return build("coverage", 0.9, target=target)

        if lower.startswith("export knowledge"):
            return build("knowledge_transfer", 0.9, mode="export")

        if lower.startswith("import knowledge"):
            bundle = lower.split(" ", 2)[2] if len(lower.split(" ")) >= 3 else "knowledge_export.json"
            return build("knowledge_transfer", 0.9, mode="import", bundle=bundle)

        if lower.startswith(("prompt lab", "prompt stats", "prompt strategy")):
            return build("prompt_lab", 0.85)

        if lower.startswith("build tool "):
            tool_name = lower.replace("build tool ", "", 1).strip()
            return build("tool_builder", 0.9, name=tool_name)

        if lower.startswith(("analyze diagram", "diagram flow", "show diagram flow")):
            diagram = user_input.split(" ", 2)[2] if len(user_input.split(" ")) >= 3 else ""
            return build("diagram_analyze", 0.9, diagram=diagram)

        if lower.startswith(("analyze schema", "schema analyze", "database schema")):
            return build("schema_analyze", 0.9)

        if lower.startswith(("visualize diff", "diff visual", "show diff graph")):
            return build("diff_visualize", 0.9)

        if lower.startswith(("architecture", "analyze architecture", "analyze design")):
            return build("architecture", 0.85)

        if lower.startswith(("generate pr", "pr draft", "create pr")):
            return build("pr", 0.9)

        if lower.startswith(("vscode setup", "vscode", "editor setup")):
            return build("vscode", 0.85)

        if lower.startswith(("dashboard", "web dashboard", "metrics dashboard")):
            return build("dashboard", 0.85)

        if lower.startswith(("learning metrics", "baseline metrics", "metrics harness")):
            return build("learning_metrics", 0.9)

        if lower.startswith(("collaborate ", "multi-agent ", "team up ")):
            task = lower.split(" ", 1)[1] if " " in lower else "general task"
            return build("multi_agent", 0.9, task=task)

        if lower.startswith(("route task ", "route ", "who should handle ")):
            task = lower.split(" ", 1)[1] if " " in lower else "general task"
            return build("agent_route", 0.85, task=task)

        if lower.startswith("agent memory"):
            topic = lower.replace("agent memory", "", 1).strip()
            return build("agent_memory", 0.85, mode="recall", topic=topic)

        if (
            lower in {"help", "hey", "hi", "hello"}
            or "what can you do" in lower
            or "capabilities" in lower
            or "what is your job" in lower
            or "who are you" in lower
            or "what's your job" in lower
        ):
            return build("help_summary", 0.95)

        if lower.startswith(("security scan", "vulnerability scan", "scan security")):
            target = lower.split(" ", 2)[-1] if lower.count(" ") >= 2 else "src/"
            return build("security_scan", 0.9, target=target)

        if lower.startswith(("generate docs", "doc generate", "generate docstrings", "list undocumented")):
            target = lower.split(" ", 2)[-1] if lower.count(" ") >= 2 else "src/"
            return build("doc_generate", 0.9, target=target)

        if lower.startswith(("generate api", "api generate", "create api")):
            target = lower.split(" ", 2)[-1] if lower.count(" ") >= 2 else "src/"
            return build("api_generate", 0.9, target=target)

        if lower.startswith(("resolve dep", "check dep", "dep resolve", "dependency")):
            return build("dep_resolve", 0.9)

        if lower.startswith(("team kb", "knowledge base", "team knowledge")):
            query = lower
            for prefix in ("team kb", "knowledge base", "team knowledge"):
                if query.startswith(prefix):
                    query = query.replace(prefix, "", 1).strip()
                    break
            return build("team_kb", 0.9, query=query)

        if lower.startswith(("audit trail", "audit log", "compliance audit")):
            return build("audit_trail", 0.9)

        if lower.startswith(("rbac", "role permissions", "check role")):
            return build("rbac", 0.9)

        if lower.startswith(("model route", "llm route", "custom model")):
            task = lower
            for prefix in ("model route", "llm route", "custom model"):
                if task.startswith(prefix):
                    task = task.replace(prefix, "", 1).strip()
                    break
            return build("custom_llm", 0.9, task=task or "general task")

        if lower.startswith(("team analytics", "analytics dashboard", "productivity metrics")):
            return build("team_analytics", 0.9)

        if lower.startswith(("language summary", "multi language", "language support")):
            target = "src/"
            parts = lower.split(" ", 2)
            if len(parts) == 3:
                target = parts[2].strip() or "src/"
            return build("multi_language", 0.9, target=target)

        if lower.startswith(("framework expert", "django expert", "fastapi expert", "react expert")):
            task = lower
            for prefix in ("framework expert", "django expert", "fastapi expert", "react expert"):
                if task.startswith(prefix):
                    task = task.replace(prefix, "", 1).strip()
                    break
            return build("framework_expert", 0.9, task=task or "general")

        if self._looks_like_code_request(lower):
            return build("generate", 0.65, instruction=user_input, stream=True)

        return build("clarify", 0.35, original_input=user_input)
