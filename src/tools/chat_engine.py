"""
Interactive chat interface for the AI coding assistant.
Understands natural language requests and routes to appropriate tools.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from src.agents.coding_agent import CodingAgent
from src.tools.autofix import run_autofix_loop
from src.tools.repo_index import build_file_index
from src.tools.semantic_retriever import retrieve_relevant_snippets
from src.tools.status_report import build_status_report
from src.tools.project_memory import remember_note, search_notes


class ChatEngine:
    """Conversational interface that understands coding requests."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.agent = CodingAgent()
        self.context = {}
        self._load_context()
    
    def _load_context(self):
        """Load repo context for smarter responses."""
        try:
            self.context["index"] = build_file_index(str(self.workspace_root))
            report = build_status_report(str(self.workspace_root))
            self.context["status"] = report
        except Exception:
            pass
    
    def parse_request(self, user_input: str) -> dict:
        """Parse natural language request and determine action."""
        lower = user_input.lower().strip()
        
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
                "confidence": 0.9
            }
        
        # Pattern: "write <description>"
        if lower.startswith("write "):
            desc = lower.replace("write ", "").strip()
            return {
                "action": "generate",
                "instruction": desc,
                "confidence": 0.85
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
            else:
                return "❓ I didn't understand that. Try: 'write <code>', 'fix <file>', 'add <feature> to <file>', 'search <query>', or 'status'"
        except Exception as e:
            return f"⚠️ Error: {str(e)[:100]}"
    
    def _handle_generate(self, request: dict) -> str:
        """Generate code from prompt."""
        instruction = request.get("instruction", "")
        code = self.agent.generate_code(instruction)
        eval_result = self.agent.evaluate_code(code)
        
        status = "✅ Success" if eval_result["execution_ok"] else "⚠️ Has issues"
        output = eval_result.get("stdout", "")[:200]
        
        return f"""Generated code:
```python
{code[:300]}...
```
{status} - Execution output: {output}"""
    
    def _handle_edit(self, request: dict) -> str:
        """Edit a file with instruction."""
        target = request.get("target", "src/main.py")
        instruction = request.get("instruction", "")
        
        target_path = self.workspace_root / target
        if not target_path.exists():
            return f"❌ File not found: {target}"
        
        return f"📝 I'll {instruction.lower()} in {target}. Use 'autofix {target}' to apply changes and test."
    
    def _handle_autofix(self, request: dict) -> str:
        """Run autofix loop on target file."""
        target = request.get("target", "src/main.py")
        instruction = request.get("instruction", "")
        
        target_path = self.workspace_root / target
        if not target_path.exists():
            return f"❌ File not found: {target}"
        
        result = run_autofix_loop(
            agent=self.agent,
            workspace_root=str(self.workspace_root),
            target_path=target,
            instruction=instruction,
            max_attempts=3
        )
        
        if result.get("success"):
            attempts = len(result.get("attempts", []))
            return f"✅ Fixed in {attempts} attempt(s)! Tests passed.\nTrace: {result.get('trace_id')}"
        else:
            return f"❌ Couldn't fix after {len(result.get('attempts', []))} attempts.\nReason: {result.get('reason', 'unknown')}"
    
    def _handle_search(self, request: dict) -> str:
        """Search codebase."""
        query = request.get("query", "")
        snippets = retrieve_relevant_snippets(str(self.workspace_root), query, limit=3)
        
        if not snippets:
            return f"🔍 No results for '{query}'"
        
        result = f"🔍 Found {len(snippets)} matches for '{query}':\n"
        for snip in snippets[:3]:
            path = snip.get("path", "unknown")[:50]
            result += f"  • {path}\n"
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
