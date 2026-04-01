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
            else:
                return "❓ I didn't understand that. Try: 'write <code>', 'fix <file>', 'add <feature> to <file>', 'search <query>', 'browse <path>', 'learn', or 'status'"
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
