"""Natural-language command parser shared by chat, CLI, and API surfaces."""

from __future__ import annotations

import re
from typing import Any, Callable

from src.tools.commanding.models import ActionRequest
from src.tools.prompt_taxonomy import classify_prompt_type


class ChatRequestParser:
    """Parse natural-language prompts into typed action requests."""

    def __init__(self, looks_like_code_request: Callable[[str], bool]):
        self._looks_like_code_request = looks_like_code_request

    @staticmethod
    def _strip_polite_prefixes(text: str) -> str:
        lowered = text.strip().lower()
        for prefix in ("please ", "can you ", "could you ", "would you "):
            if lowered.startswith(prefix):
                return lowered[len(prefix):].strip()
        return lowered

    @staticmethod
    def _looks_like_path(text: str) -> bool:
        candidate = text.strip().strip("`'\"")
        if not candidate:
            return False
        if "/" in candidate or candidate.startswith((".", "src", "tests", "vscode-extension", ".vscode")):
            return True
        if re.search(r"\.[a-z0-9]{1,8}$", candidate.lower()):
            return True
        return candidate.lower() in {
            "readme",
            "readme.md",
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "tasks.json",
            "launch.json",
        }

    def _looks_like_actionable_request(self, lower: str) -> bool:
        normalized = self._strip_polite_prefixes(lower)
        action_prefixes = (
            "add ",
            "build ",
            "create ",
            "implement ",
            "support ",
            "allow ",
            "make ",
            "improve ",
            "enable ",
            "introduce ",
            "give me ",
            "let's add ",
        )
        if not normalized.startswith(action_prefixes):
            return False

        if normalized.startswith(
            (
                "build tool ",
                "build itself",
                "self build",
                "build myself",
                "improve myself",
                "self improve",
                "self-improve",
                "create pr",
                "generate api",
                "generate docs",
            )
        ):
            return False

        code_only_markers = ("function", "class", "method", "endpoint", "sql query", "unit test")
        if any(marker in normalized for marker in code_only_markers):
            return False

        return True

    @staticmethod
    def _looks_like_web_request(lower: str) -> bool:
        return any(
            phrase in lower
            for phrase in (
                "use the web",
                "use web",
                "search the web",
                "look online",
                "online docs",
                "web research",
                "check documentation online",
            )
        )

    @staticmethod
    def _looks_like_self_awareness_request(lower: str) -> bool:
        return any(
            phrase in lower
            for phrase in (
                "self aware",
                "self-aware",
                "what can you actually execute",
                "what commands can you execute",
                "what features can you execute",
                "can you use the web",
                "is the server up",
                "is ollama reachable",
                "where is the vs code panel",
                "where is the vscode panel",
            )
        )

    @staticmethod
    def _looks_like_capability_request(lower: str) -> bool:
        return any(
            phrase in lower
            for phrase in (
                "what can you do",
                "what is your job",
                "what's your job",
                "who are you",
                "name 5 things you can do",
                "name five things you can do",
                "what are 5 things you can do",
                "what are five things you can do",
                "one thing you can do",
                "one improvement you can make",
                "what improvement you can make",
                "improvement you can make",
                "improve on how you talk",
                "talk to me like a human",
                "talk to users",
            )
        )

    def parse(self, user_input: str) -> ActionRequest:
        lower = user_input.lower().strip()
        normalized = self._strip_polite_prefixes(user_input)

        def build(action: str, confidence: float, **params: Any) -> ActionRequest:
            return ActionRequest(
                action=action,
                confidence=confidence,
                raw_input=user_input,
                params=params,
            )

        if lower.startswith(("browse ", "ls ")):
            parts = lower.split(" ", 1)
            path = parts[1] if len(parts) > 1 else "."
            return build("browse", 0.95, path=path)

        if lower.startswith(("show ", "open ")):
            parts = user_input.split(" ", 1)
            path = parts[1] if len(parts) > 1 else "."
            if self._looks_like_path(path):
                return build("browse", 0.95, path=path)

        if self._looks_like_self_awareness_request(lower):
            return build("self_aware_summary", 0.92)

        if lower in {"help", "hey", "hi", "hello"} or self._looks_like_capability_request(lower):
            return build("help_summary", 0.95)

        if self._looks_like_web_request(lower):
            return build("research", 0.88, goal=user_input, prefer_web=True)

        if normalized.startswith("self-improve plan "):
            goal = re.sub(
                r"^(?:please |can you |could you |would you )?self-improve plan\s+",
                "",
                user_input.strip(),
                flags=re.IGNORECASE,
            ).strip()
            return build("self_improve_plan", 0.96, goal=goal, prefer_web=self._looks_like_web_request(lower))

        if normalized.startswith("self-improve run "):
            goal = re.sub(
                r"^(?:please |can you |could you |would you )?self-improve run\s+",
                "",
                user_input.strip(),
                flags=re.IGNORECASE,
            ).strip()
            return build("self_improve_run", 0.96, goal=goal, prefer_web=self._looks_like_web_request(lower))

        if normalized.startswith("approve self-improve "):
            run_id = re.sub(
                r"^(?:please |can you |could you |would you )?approve self-improve\s+",
                "",
                user_input.strip(),
                flags=re.IGNORECASE,
            ).strip()
            return build("self_improve_apply", 0.97, run_id=run_id)

        if normalized.startswith("self-improve apply "):
            run_id = re.sub(
                r"^(?:please |can you |could you |would you )?self-improve apply\s+",
                "",
                user_input.strip(),
                flags=re.IGNORECASE,
            ).strip()
            return build("self_improve_apply", 0.97, run_id=run_id)

        if normalized in {"self-improve status", "self improve status"}:
            return build("self_improve_status", 0.95)

        if normalized.startswith("self-improve status "):
            run_id = re.sub(
                r"^(?:please |can you |could you |would you )?self-improve status\s+",
                "",
                user_input.strip(),
                flags=re.IGNORECASE,
            ).strip()
            return build("self_improve_status", 0.95, run_id=run_id)

        if lower.startswith(("research ", "investigate ")):
            goal = user_input.split(" ", 1)[1] if " " in user_input else user_input
            return build("research", 0.9, goal=goal, prefer_web=self._looks_like_web_request(lower))

        if lower.startswith("add "):
            parts = user_input.split(" to ", 1)
            if len(parts) == 2:
                feature = parts[0].replace("add ", "", 1).strip()
                target = parts[1].strip()
                if self._looks_like_path(target):
                    return build(
                        "edit",
                        0.85,
                        target=target,
                        instruction=f"Add {feature}",
                    )
                return build(
                    "research",
                    0.88,
                    goal=user_input,
                    feature=feature,
                    target=target,
                    prefer_web=self._looks_like_web_request(lower),
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

        if self._looks_like_actionable_request(lower):
            return build("research", 0.78, goal=user_input, prefer_web=self._looks_like_web_request(lower))

        if lower.startswith(("search ", "find ", "where ")):
            query = lower.split(" ", 1)[1] if " " in lower else ""
            return build("search", 0.8, query=query)

        if lower.startswith(
            ("readiness", "run canaries", "run canary", "self improvement readiness", "self-improvement readiness")
        ):
            return build("readiness", 0.92)

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

        if "capabilities" in lower:
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

        if self._looks_like_code_request(normalized):
            return build("generate", 0.65, instruction=user_input, stream=True)

        if any(term in normalized for term in ("panel", "extension", "workspace", "command history", "click-to-replay")):
            return build("research", 0.7, goal=user_input, prefer_web=self._looks_like_web_request(lower))

        return build("clarify", 0.35, original_input=user_input)
