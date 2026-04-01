"""
Interactive chat interface with streaming, markdown, and file browsing.
Understands natural language requests and routes to appropriate tools.
Integrates online documentation and learns from interactions.
Self-improves using specialized knowledge built from experience.
"""

import json
import sys
import os
from pathlib import Path
from typing import Optional, Generator

from src.agents.coding_agent import CodingAgent
from src.tools.autofix import run_autofix_loop
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.status_report import build_status_report
from src.tools.project_memory import remember_note, search_notes
from src.tools.doc_fetcher import DocFetcher, enhance_with_docs
from src.tools.self_builder import SelfBuilder
from src.tools.code_reviewer import CodeReviewer, format_review_report
from src.tools.debugger import PythonDebugger, format_debug_output
from src.tools.profiler import CodeProfiler, format_profile_output
from src.tools.coverage_analyzer import TestCoverageAnalyzer, format_coverage_output
from src.tools.knowledge_transfer import KnowledgeTransfer
from src.tools.prompt_lab import PromptLab
from src.tools.tool_builder import ToolBuilder
from src.tools.architecture_analyzer import ArchitectureAnalyzer


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
            # Code blocks
            if line.strip().startswith("```"):
                in_code = not in_code
                if in_code:
                    rendered.append(f"\n{cls.DIM}─────────────────────{cls.RESET}")
                else:
                    rendered.append(f"{cls.DIM}─────────────────────{cls.RESET}\n")
                continue
            
            if in_code:
                rendered.append(f"{cls.CYAN}{line}{cls.RESET}")
            # Headers
            elif line.startswith("# "):
                rendered.append(f"{cls.BOLD}{cls.MAGENTA}{line[2:]}{cls.RESET}")
            elif line.startswith("## "):
                rendered.append(f"{cls.BOLD}{cls.BLUE}{line[3:]}{cls.RESET}")
            elif line.startswith("### "):
                rendered.append(f"{cls.BOLD}{line[4:]}{cls.RESET}")
            # Bold/Italic
            elif "**" in line:
                rendered.append(f"{cls.BOLD}{line.replace('**', '')}{cls.RESET}")
            # Bullet points
            elif line.startswith("- "):
                rendered.append(f"{cls.GREEN}•{cls.RESET} {line[2:]}")
            elif line.startswith("  - "):
                rendered.append(f"{cls.GREEN}  ◦{cls.RESET} {line[4:]}")
            # Success/Warning/Error indicators
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
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.agent = CodingAgent()
        self.context = {}
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
        self.interaction_log = []  # Track interactions for learning
        self._load_context()
    
    def _load_context(self):
        """Load repo context for smarter responses."""
        try:
            self.context["index"] = build_file_index(str(self.workspace_root))
            report = build_status_report(str(self.workspace_root))
            self.context["status"] = report
            
            # Index documentation for packages in the project
            packages = self.doc_fetcher.extract_requirements(str(self.workspace_root / "pyproject.toml"))
            if not packages:
                packages = self.doc_fetcher.extract_requirements(str(self.workspace_root / "requirements.txt"))
            if packages:
                self.doc_fetcher.index_library(packages)
                self.context["packages"] = packages
            
            # Load learned knowledge
            kb = self.self_builder.export_knowledge_base()
            self.context["knowledge_base"] = kb
        except Exception:
            pass
    
        def _handle_debug(self, request: dict) -> str:
            """Debug code with execution tracing and breakpoints."""
            target = request.get("target", "src/main.py")
        
            target_path = self.workspace_root / target
            if not target_path.exists():
                return f"❌ File not found: {target}"
        
            if target_path.is_file() and target.endswith(".py"):
                print(f"\n🐛 Analyzing {target} for debugging...\n", flush=True)
            
                # Start debug session
                session_result = self.debugger.start_debug_session(target)
                if "error" in session_result:
                    return f"❌ {session_result['error']}"
            
                # Get execution trace
                trace = self.debugger.trace_execution(target)
                call_analysis = self.debugger.analyze_call_patterns(target)
            
                # Format output
                output = f"""🐛 Debug Session: {target}
    {session_result['message']}

    """
            
                if "functions" in trace and trace["functions"]:
                    output += f"🔵 Functions (Total: {trace['total_functions']}):\n"
                    for func_name, line_num in trace['functions'][:10]:
                        output += f"  • {func_name} (line {line_num})\n"
                    if len(trace['functions']) > 10:
                        output += f"  ... and {len(trace['functions']) - 10} more\n"
            
                output += f"""
    📊 Call Analysis:
      Internal Calls: {len(call_analysis.get('internal_calls', []))}
      External Calls: {len(call_analysis.get('external_calls', []))}

    💡 Use 'breakpoint <line>' to set breakpoints, 'inspect' to view code, or 'learn' for improvements"""
            
                self._log_interaction(f"debug {target}", "debug", True)
                return output
        
            return f"❌ Target must be a Python file: {target}"
    
    
        def _handle_profile(self, request: dict) -> str:
            """Profile code performance and identify bottlenecks."""
            target = request.get("target", "src/")
        
            target_path = self.workspace_root / target
        
            print(f"\n⚡ Profiling {target}...\n", flush=True)
        
            if target.endswith("/") or (target_path.exists() and target_path.is_dir()):
                # Profile directory - analyze all files
                complexity = self.profiler.analyze_complexity(target.rstrip("/") + ".py" if target.endswith("/") else target)
            
                if "error" in complexity:
                    optimization = self.profiler.suggest_optimizations(target_path.parent / "*.py")
                    if "error" in optimization:
                        return f"❌ Unable to profile: {target}"
                    return format_profile_output(optimization)
            
                suggestions = self.profiler.suggest_optimizations(str(target_path / "*.py") if target.endswith("/") else target)
            
                output = f"""⚡ Performance Profile: {target}

    🎯 Complexity Rating: {complexity.get('complexity_rating', 'Unknown')}

    💡 Optimization Suggestions:
    """
            
                if "suggestions" in suggestions:
                    for i, sugg in enumerate(suggestions["suggestions"][:5], 1):
                        output += f"\n{i}. {sugg['category']} ({sugg['priority'].upper()})\n"
                        output += f"   Problem: {sugg['issue']}\n"
                        output += f"   Solution: {sugg['suggestion']}\n"
                        output += f"   Impact: {sugg['potential_speedup']}\n"
            
                self._log_interaction(f"profile {target}", "profile", True)
                return output
        
            # Single file profiling
            if not target_path.exists():
                return f"❌ File not found: {target}"
        
            if target_path.is_file() and target.endswith(".py"):
                hotspots = self.profiler.profile_function_calls(target)
                complexity = self.profiler.analyze_complexity(target)
            
                if "error" in hotspots:
                    return f"❌ {hotspots['error']}"
            
                formatted = format_profile_output(hotspots)
                complexity_formatted = format_profile_output(complexity)
            
                self._log_interaction(f"profile {target}", "profile", True)
                return f"{formatted}\n\n{complexity_formatted}"
        
            return f"❌ Target must be a Python file or directory: {target}"
    
    
        def _handle_coverage(self, request: dict) -> str:
            """Show test coverage and suggest missing tests."""
            target = request.get("target", "src/")
        
            target_path = self.workspace_root / target
        
            print(f"\n📊 Analyzing test coverage for {target}...\n", flush=True)
        
            if target.endswith("/") or (target_path.exists() and target_path.is_dir()):
                # Batch coverage analysis
                output = f"""📊 Test Coverage Analysis: {target}

    """
            
                # Find all Python files and analyze coverage
                py_files = list((self.workspace_root / target).glob("*.py"))
                if not py_files:
                    py_files = list((self.workspace_root / target).glob("**/*.py"))
            
                coverage_dict = {}
                total_coverage = 0
            
                for py_file in py_files[:5]:
                    rel_path = py_file.relative_to(self.workspace_root)
                    analysis = self.coverage_analyzer.analyze_file(str(rel_path))
                    if "coverage_percentage" in analysis:
                        coverage_dict[str(rel_path)] = analysis["coverage_percentage"]
                        total_coverage += analysis["coverage_percentage"]
            
                if coverage_dict:
                    avg_coverage = total_coverage / len(coverage_dict)
                    report = self.coverage_analyzer.coverage_report(coverage_dict)
                    formatted = format_coverage_output(report)
                
                    self._log_interaction(f"coverage {target}", "coverage", True)
                    return formatted
            
                return f"❌ No Python files found in {target}"
        
            # Single file coverage
            if not target_path.exists():
                return f"❌ File not found: {target}"
        
            if target_path.is_file() and target.endswith(".py"):
                analysis = self.coverage_analyzer.analyze_file(target)
                suggestions = self.coverage_analyzer.suggest_missing_tests(target)
            
                if "error" in analysis:
                    return f"❌ {analysis['error']}"
            
                formatted = format_coverage_output(analysis)
            
                if "suggestions" in suggestions:
                    test_suggestions = format_coverage_output(suggestions)
                    formatted = f"{formatted}\n\n{test_suggestions}"
            
                self._log_interaction(f"coverage {target}", "coverage", True)
                return formatted
        
            return f"❌ Target must be a Python file or directory: {target}"
    def _log_interaction(self, query: str, action: str, success: bool, doc_context: Optional[str] = None):
        """Log interaction for learning and improvement."""
        self.interaction_log.append({
            "query": query,
            "action": action,
            "success": success,
            "doc_context": doc_context,
            "timestamp": str(Path.home() / ".dev_timestamp")
        })
    def parse_request(self, user_input: str) -> dict:
        """Parse natural language request and determine action."""
        lower = user_input.lower().strip()
        
        # File browsing: "browse <path>", "ls <path>", "show <path>"
        if any(lower.startswith(cmd) for cmd in ["browse ", "ls ", "show ", "open "]):
            parts = lower.split(" ", 1)
            path = parts[1] if len(parts) > 1 else "."
            return {
                "action": "browse",
                "path": path,
                "confidence": 0.95
            }
        
        # Patterns: "add <feature> to <file>"
        if lower.startswith("add "):
            parts = lower.split(" to ")
            if len(parts) == 2:
                feature = parts[0].replace("add ", "").strip()
                target = parts[1].strip()
                return {
                    "action": "edit",
                    "target": target,
                    "instruction": f"Add {feature}",
                    "confidence": 0.85
                }
        
        # Pattern: "fix <target>"
        if lower.startswith("fix "):
            target = lower.replace("fix ", "").strip()
            return {
                "action": "autofix",
                "target": target,
                "instruction": f"Fix issues in {target}",
                "confidence": 0.9,
                "stream": True
            }
        
        # Pattern: "write <description>"
        if lower.startswith("write "):
            desc = lower.replace("write ", "").strip()
            return {
                "action": "generate",
                "instruction": desc,
                "confidence": 0.85,
                "stream": True
            }
        
        # Pattern: "search/find <query>"
        if lower.startswith(("search ", "find ", "where ")):
            query = lower.split(" ", 1)[1] if " " in lower else ""
            return {
                "action": "search",
                "query": query,
                "confidence": 0.8
            }
        
        # Pattern: "status/how are we doing"
        if any(w in lower for w in ["status", "score", "how are we", "progress", "health"]):
            return {
                "action": "status",
                "confidence": 0.95
            }
        
        # Pattern: "remember/note <key> <value>"
        if lower.startswith(("remember ", "note ")):
            rest = lower.split(" ", 1)[1]
            return {
                "action": "remember",
                "memory": rest,
                "confidence": 0.8
            }
        
        # Pattern: "learn/improve/self-improve"
        if any(w in lower for w in ["learn", "improve myself", "self-improve", "self improve", "build myself"]):
            return {
                "action": "learn",
                "confidence": 0.9
            }
        
        # Pattern: "review <file>" or "check <file>"
        if lower.startswith(("review ", "check ", "audit ")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return {
                "action": "review",
                "target": target,
                "confidence": 0.9
            }
        
        # Pattern: "debug <file>" or "trace <file>"
        if lower.startswith(("debug ", "trace ", "step ")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/main.py"
            return {
                "action": "debug",
                "target": target,
                "confidence": 0.9
            }
        
        # Pattern: "profile <file>" or "benchmark <file>"
        if lower.startswith(("profile ", "optimize ")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return {
                "action": "profile",
                "target": target,
                "confidence": 0.9
            }
        
        # Pattern: "coverage <file>" or "test <file>"
        if lower.startswith(("coverage ", "test coverage")):
            target = lower.split(" ", 1)[1] if " " in lower else "src/"
            return {
                "action": "coverage",
                "target": target,
                "confidence": 0.9
            }

        # Pattern: "export knowledge" / "import knowledge <file>"
        if lower.startswith("export knowledge"):
            return {
                "action": "knowledge_transfer",
                "mode": "export",
                "confidence": 0.9,
            }

        if lower.startswith("import knowledge"):
            bundle = lower.split(" ", 2)[2] if len(lower.split(" ")) >= 3 else "knowledge_export.json"
            return {
                "action": "knowledge_transfer",
                "mode": "import",
                "bundle": bundle,
                "confidence": 0.9,
            }

        # Pattern: "prompt lab" / "prompt stats"
        if lower.startswith(("prompt lab", "prompt stats", "prompt strategy")):
            return {
                "action": "prompt_lab",
                "confidence": 0.85,
            }

        # Pattern: "build tool <name>"
        if lower.startswith("build tool "):
            tool_name = lower.replace("build tool ", "", 1).strip()
            return {
                "action": "tool_builder",
                "name": tool_name,
                "confidence": 0.9,
            }

        # Pattern: "architecture" / "analyze architecture"
        if lower.startswith(("architecture", "analyze architecture", "analyze design")):
            return {
                "action": "architecture",
                "confidence": 0.85,
            }
        
        # Fallback: treat as code generation
        return {
            "action": "generate",
            "instruction": user_input,
            "confidence": 0.6
        }
    
    def execute(self, request: dict) -> str:
        """Execute parsed request and return conversational response."""
        action = request.get("action", "generate")
        
        try:
            if action == "generate":
                return self._handle_generate(request)
            elif action == "edit":
                return self._handle_edit(request)
            elif action == "autofix":
                return self._handle_autofix(request)
            elif action == "search":
                return self._handle_search(request)
            elif action == "status":
                return self._handle_status(request)
            elif action == "remember":
                return self._handle_remember(request)
            elif action == "browse":
                return self._handle_browse(request)
            elif action == "learn":
                return self._handle_learn(request)
            elif action == "review":
                return self._handle_review(request)
            elif action == "debug":
                return self._handle_debug(request)
            elif action == "profile":
                return self._handle_profile(request)
            elif action == "coverage":
                return self._handle_coverage(request)
            elif action == "knowledge_transfer":
                return self._handle_knowledge_transfer(request)
            elif action == "prompt_lab":
                return self._handle_prompt_lab(request)
            elif action == "tool_builder":
                return self._handle_tool_builder(request)
            elif action == "architecture":
                return self._handle_architecture(request)
            else:
                return "❓ I didn't understand that. Try: 'write <code>', 'fix <file>', 'review <file>', 'debug <file>', 'profile <file>', 'coverage <file>', 'export knowledge', 'import knowledge <file>', 'prompt lab', 'build tool <name>', 'architecture', 'search <query>', 'browse <path>', 'learn', or 'status'"
        except Exception as e:
            return f"⚠️ Error: {str(e)[:100]}"
    
    def _handle_generate(self, request: dict) -> str:
        """Generate code from prompt with streaming output and doc context."""
        instruction = request.get("instruction", "")
        use_streaming = request.get("stream", True)
        
        # Enhance with documentation context
        doc_context = enhance_with_docs(str(self.workspace_root), instruction)
        
        if use_streaming:
            if doc_context:
                print(doc_context, flush=True)
                print()
            print("🔄 Generating... ", end="", flush=True)
        
        code = self.agent.generate_code(instruction)
        
        if use_streaming:
            print("\n\n📄 Code generated:", flush=True)
            print("```python")
            print(code)
            print("```\n")
            print("🧪 Testing... ", end="", flush=True)
        
        eval_result = self.agent.evaluate_code(code)
        
        if use_streaming:
            print("Done!\n", flush=True)
        
        status = "✅ Success" if eval_result["execution_ok"] else "⚠️ Has issues"
        output = eval_result.get("stdout", "")
        
        # Log interaction for learning
        self._log_interaction(instruction, "generate", eval_result["execution_ok"], doc_context)
        
        return f"""{status}
Execution output:
{output}"""
    
    def _handle_edit(self, request: dict) -> str:
        """Edit a file with instruction."""
        target = request.get("target", "src/main.py")
        instruction = request.get("instruction", "")
        
        target_path = self.workspace_root / target
        if not target_path.exists():
            return f"❌ File not found: {target}"
        
        return f"📝 I'll {instruction.lower()} in {target}. Use 'autofix {target}' to apply changes and test."
    
    def _handle_autofix(self, request: dict) -> str:
        """Run autofix loop on target file with streaming feedback and doc context."""
        target = request.get("target", "src/main.py")
        instruction = request.get("instruction", "")
        use_streaming = request.get("stream", True)
        
        target_path = self.workspace_root / target
        if not target_path.exists():
            return f"❌ File not found: {target}"
        
        # Enhance with documentation context
        doc_context = enhance_with_docs(str(self.workspace_root), instruction)
        
        if use_streaming:
            if doc_context:
                print(doc_context, flush=True)
                print()
            print(f"🔧 Running autofix on {target}... ", flush=True)
            print(f"   Instruction: {instruction}\n")
        
        result = run_autofix_loop(
            agent=self.agent,
            workspace_root=str(self.workspace_root),
            target_path=target,
            instruction=instruction,
            max_attempts=3
        )
        
        if use_streaming:
            print()
        
        success = result.get("success", False)
        if success:
            attempts = len(result.get("attempts", []))
            if use_streaming:
                print(f"✅ Success! Fixed in {attempts} attempt(s)", flush=True)
            self._log_interaction(f"fix {target}", "autofix", True, doc_context)
            return f"✅ Fixed in {attempts} attempt(s)! Tests passed.\nTrace: {result.get('trace_id')}"
        else:
            if use_streaming:
                print(f"❌ Couldn't fix after {len(result.get('attempts', []))} attempts", flush=True)
            self._log_interaction(f"fix {target}", "autofix", False, doc_context)
            return f"❌ Couldn't fix after {len(result.get('attempts', []))} attempts.\nReason: {result.get('reason', 'unknown')}"
    
    def _handle_search(self, request: dict) -> str:
        """Search codebase with doc suggestions."""
        query = request.get("query", "")
        snippets = retrieve_relevant_snippets(str(self.workspace_root), query, limit=3)
        
        # Enhance with relevant documentation
        doc_context = enhance_with_docs(str(self.workspace_root), query)
        
        result = ""
        if doc_context:
            result += doc_context + "\n\n"
        
        if not snippets:
            self._log_interaction(f"search {query}", "search", False)
            return f"{result}🔍 No code results for '{query}'" if result else f"🔍 No results for '{query}'"
        
        result += f"🔍 Found {len(snippets)} matches for '{query}':\n"
        for snip in snippets[:3]:
            path = snip.get("path", "unknown")[:50]
            result += f"  • {path}\n"
        
        self._log_interaction(f"search {query}", "search", True, doc_context)
        return result
    
    def _handle_status(self, request: dict) -> str:
        """Show project status."""
        if "status" not in self.context:
            return "📊 Unable to load status"
        
        status = self.context["status"]
        readiness = status.get("readiness", "unknown")
        score = status.get("benchmark", {}).get("score", "N/A")
        
        return f"""📊 Project Status:
  Readiness: {readiness}
  Benchmark Score: {score}
  Roadmap: {status.get('roadmap', {}).get('percent', 'N/A')}% complete"""
    
    def _handle_remember(self, request: dict) -> str:
        """Store a note in project memory."""
        memory = request.get("memory", "")
        key = memory.split(" ")[0] if memory else "note"
        value = " ".join(memory.split(" ")[1:]) if " " in memory else memory
        
        remember_note(str(self.workspace_root), key=key, value=value)
        return f"✅ Remembered: {key} = {value}"
    
    def _handle_learn(self, request: dict) -> str:
        """Trigger self-improvement cycle based on learned interactions."""
        print("\n📚 Analyzing interactions and building knowledge...\n", flush=True)
        
        # Learn from logged interactions
        if self.interaction_log:
            print(f"📊 Processing {len(self.interaction_log)} interactions...", flush=True)
            self.self_builder.learn_from_logs(self.interaction_log)
        
        # Get improvement plan
        plan = self.self_builder.generate_self_improvement_plan(self.interaction_log)
        
        # Display knowledge built
        kb = self.self_builder.export_knowledge_base()
        
        result = f"""✨ Self-Improvement Complete!

📈 Learning Results:
  • Success Rate: {kb['metrics'].get('success_rate', 0):.1%}
  • Total Interactions: {kb['metrics'].get('interaction_count', 0)}
  • Solutions Cached: {len(kb['solutions'])}
  • Strategies Learned: {len(kb['strategies'])}

🎯 Improvement Plan:
  • Current Success Rate: {plan['current_success_rate']:.1%}
  • Target: {plan['target_success_rate']:.1%}
  • Estimated Cycles Needed: {plan['estimated_cycles']}

💡 Recommendations:
"""
        
        suggestions = self.self_builder.get_improvement_suggestions()
        for suggestion in suggestions:
            result += f"  • {suggestion}\n"
        
        result += f"""
✅ Knowledge Base:
  • Solutions can guide future code generation
  • Strategies optimize action selection
  • Patterns prevent repeated failures
  • Context-aware responses improve over time
"""
        
        return result
    
    def _handle_browse(self, request: dict) -> str:
        """Browse files and directories."""
        path = request.get("path", ".")
        target = self.workspace_root / path if path != "." else self.workspace_root
        
        # Normalize and validate path (prevent directory traversal)
        try:
            target = target.resolve()
            if not str(target).startswith(str(self.workspace_root.resolve())):
                return f"❌ Access denied: outside workspace"
        except Exception:
            return f"❌ Invalid path: {path}"
        
        if not target.exists():
            return f"❌ Not found: {path}"
        
        # Show file contents if it's a file
        if target.is_file():
            try:
                with open(target, 'r') as f:
                    content = f.read()
                
                # Show with line numbers for reasonable-sized files
                lines = content.split('\n')
                if len(lines) <= 100:
                    numbered = "\n".join(f"{i+1:3d} | {line}" for i, line in enumerate(lines))
                    return f"""📄 {target.name} ({len(lines)} lines):
```
{numbered[:2000]}
```"""
                else:
                    return f"""📄 {target.name} ({len(lines)} lines) - Too long to display.
First 50 lines:
```
{chr(10).join(f"{i+1:3d} | {line}" for i, line in enumerate(lines[:50]))}
```
Use 'show <file> 50-100' to see specific lines."""
            except Exception as e:
                return f"❌ Can't read {path}: {str(e)[:50]}"
        
        # Show directory contents
        if target.is_dir():
            items = []
            try:
                for item in sorted(target.iterdir()):
                    if item.name.startswith('.'):
                        continue  # Skip hidden files
                    
                    rel_path = item.relative_to(self.workspace_root)
                    if item.is_dir():
                        items.append(f"📁 {rel_path}/")
                    else:
                        size = item.stat().st_size
                        size_str = f"{size/1024:.1f}KB" if size > 1024 else f"{size}B"
                        items.append(f"📄 {rel_path} ({size_str})")
            except PermissionError:
                return f"❌ Permission denied: {path}"
            
            if not items:
                return f"📁 {path}/ (empty)"
            
            return f"""📁 {path}/:
{chr(10).join(f"  {item}" for item in items[:30])}
{f"... and {len(items)-30} more" if len(items) > 30 else ""}"""
        
        return f"❌ Unknown error browsing {path}"    
    def _handle_review(self, request: dict) -> str:
        """Review code quality, security, and best practices."""
        target = request.get("target", "src/")
        
        target_path = self.workspace_root / target
        
        # If target is a directory, review all Python files in it
        if target.endswith("/") or target_path.is_dir():
            pattern = f"{target}**/*.py" if target.endswith("/") else f"{target}/**/*.py"
            report = self.code_reviewer.review_codebase(include_patterns=[pattern])
            
            result = f"""📋 Code Review: {target}
🔍 Analyzed {report['files_reviewed']} files
📊 Average Quality Score: {report['codebase_score']:.1f}/100

Top Issues by File:
"""
            
            for filepath, file_report in list(report['reviews'].items())[:5]:
                if 'error' not in file_report:
                    score = file_report.get('quality_score', 0)
                    issues = file_report.get('total_issues', 0)
                    result += f"  • {filepath}: {score:.0f}/100 ({issues} issues)\n"
            
            if len(report['reviews']) > 5:
                result += f"  ... and {len(report['reviews']) - 5} more files\n"
            
            self._log_interaction(f"review {target}", "review", True)
            return result
        
        # Single file review
        if not target_path.exists():
            return f"❌ File not found: {target}"
        
        if target_path.is_file() and target.endswith(".py"):
            print("\n📋 Reviewing code...\n", flush=True)
            report = self.code_reviewer.review_file(target)
            
            if "error" in report:
                return f"❌ {report['error']}"
            
            # Format and display report
            formatted = format_review_report(report)
            self._log_interaction(f"review {target}", "review", True)
            return formatted
        
        return f"❌ Target must be a Python file or directory: {target}"

    def _handle_knowledge_transfer(self, request: dict) -> str:
        """Export/import knowledge base for sharing."""
        mode = request.get("mode", "export")
        if mode == "export":
            result = self.knowledge_transfer.export_bundle("knowledge_export.json")
            self._log_interaction("export knowledge", "knowledge_transfer", True)
            return f"✅ Knowledge exported to {result.get('path')} ({result.get('file_count')} files)"

        bundle = request.get("bundle", "knowledge_export.json")
        result = self.knowledge_transfer.import_bundle(bundle)
        if "error" in result:
            self._log_interaction(f"import knowledge {bundle}", "knowledge_transfer", False)
            return f"❌ {result['error']}"
        self._log_interaction(f"import knowledge {bundle}", "knowledge_transfer", True)
        return f"✅ Knowledge imported from {result.get('bundle')} ({result.get('imported_files')} files)"

    def _handle_prompt_lab(self, request: dict) -> str:
        """Show prompt strategy metrics and recommendation."""
        summary = self.prompt_lab.summarize()
        recommendation = self.prompt_lab.recommend_strategy("general coding task")

        lines = [
            "🧪 Prompt Lab",
            f"  • Total Runs: {summary.get('total_runs', 0)}",
            f"  • Overall Success: {summary.get('overall_success_rate', 0):.1%}",
            f"  • Recommended Strategy: {recommendation.get('strategy')} ({recommendation.get('reason')})",
        ]
        self._log_interaction("prompt lab", "prompt_lab", True)
        return "\n".join(lines)

    def _handle_tool_builder(self, request: dict) -> str:
        """Create a custom tool scaffold."""
        name = request.get("name", "custom_tool")
        result = self.tool_builder.create_tool(name, f"Generated tool: {name}")
        if "error" in result:
            self._log_interaction(f"build tool {name}", "tool_builder", False)
            return f"❌ {result['error']}"

        self._log_interaction(f"build tool {name}", "tool_builder", True)
        return f"✅ Tool created: {result['tool']} with test {result['test']}"

    def _handle_architecture(self, request: dict) -> str:
        """Analyze codebase architecture and recommendations."""
        result = self.architecture_analyzer.analyze("src")
        if "error" in result:
            self._log_interaction("architecture", "architecture", False)
            return f"❌ {result['error']}"

        recommendations = result.get("recommendations", [])
        self._log_interaction("architecture", "architecture", True)
        return f"""🏗️ Architecture Analysis
  • Python Files: {result.get('python_files', 0)}
  • Modules Indexed: {len(result.get('modules', []))}
  • Recommendations: {len(recommendations)}

{chr(10).join(f"  • {item}" for item in recommendations[:5])}"""

def run_chat_session(workspace_root: str = "."):
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
                print("""
Examples:
  > write a function that reverses strings
  > add type hints to src/main.py
  > fix src/utils.py
  > search for get_user_by_id
  > status
  > remember lesson always test edge cases
                """)
                continue
            
            request = engine.parse_request(user_input)
            response = engine.execute(request)
            print(f"🤖 {response}\n")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"⚠️ Error: {str(e)}\n")
