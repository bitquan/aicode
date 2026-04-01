"""
Interactive Python Debugger - Step through code, inspect variables, set breakpoints.
Provides chat-friendly debugging interface using pdb under the hood.
"""

import pdb
import sys
import io
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from contextlib import redirect_stdout, redirect_stderr


class DebugSession:
    """Represents an active debugging session."""
    
    def __init__(self, filepath: str, workspace_root: str = "."):
        self.filepath = Path(filepath)
        self.workspace_root = Path(workspace_root).resolve()
        self.breakpoints: Dict[int, bool] = {}  # line_number -> is_enabled
        self.current_line = 0
        self.variables = {}
        self.stack_trace = []
        self.is_running = False
        self.output = []
        self._validate_path()
    
    def _validate_path(self):
        """Validate file exists and is in workspace."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")
        
        resolved = self.filepath.resolve()
        if not str(resolved).startswith(str(self.workspace_root)):
            raise PermissionError(f"File outside workspace: {self.filepath}")
    
    def set_breakpoint(self, line: int) -> Dict:
        """Set a breakpoint at a specific line."""
        self.breakpoints[line] = True
        return {
            "breakpoint": line,
            "status": "set",
            "message": f"Breakpoint set at line {line}"
        }
    
    def clear_breakpoint(self, line: int) -> Dict:
        """Clear a breakpoint."""
        if line in self.breakpoints:
            del self.breakpoints[line]
            return {
                "breakpoint": line,
                "status": "cleared",
                "message": f"Breakpoint cleared at line {line}"
            }
        return {
            "error": f"No breakpoint at line {line}"
        }
    
    def clear_all_breakpoints(self) -> Dict:
        """Clear all breakpoints."""
        count = len(self.breakpoints)
        self.breakpoints.clear()
        return {
            "status": "cleared_all",
            "count": count,
            "message": f"Cleared {count} breakpoint(s)"
        }
    
    def list_breakpoints(self) -> Dict:
        """List all breakpoints."""
        return {
            "count": len(self.breakpoints),
            "breakpoints": sorted(self.breakpoints.keys()),
            "message": f"Total: {len(self.breakpoints)} breakpoint(s)"
        }


class PythonDebugger:
    """Python code debugger with chat interface."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.sessions: Dict[str, DebugSession] = {}
        self.current_session: Optional[str] = None
    
    def start_debug_session(self, filepath: str, entry_point: Optional[str] = None) -> Dict:
        """Start a new debug session."""
        try:
            file_path = Path(filepath)
            if not file_path.is_absolute():
                file_path = self.workspace_root / file_path

            session = DebugSession(str(file_path), str(self.workspace_root))
            session_id = filepath
            self.sessions[session_id] = session
            self.current_session = session_id
            
            # Read the file to show context
            with open(file_path) as f:
                lines = f.readlines()
            
            return {
                "status": "session_started",
                "filepath": filepath,
                "session_id": session_id,
                "total_lines": len(lines),
                "message": f"Debug session started for {filepath} ({len(lines)} lines)"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def set_breakpoint(self, line: int, session_id: Optional[str] = None) -> Dict:
        """Set breakpoint in current or specified session."""
        session_id = session_id or self.current_session
        if not session_id or session_id not in self.sessions:
            return {"error": "No active debug session"}
        
        session = self.sessions[session_id]
        return session.set_breakpoint(line)
    
    def clear_breakpoint(self, line: int, session_id: Optional[str] = None) -> Dict:
        """Clear breakpoint."""
        session_id = session_id or self.current_session
        if not session_id or session_id not in self.sessions:
            return {"error": "No active debug session"}
        
        session = self.sessions[session_id]
        return session.clear_breakpoint(line)
    
    def list_breakpoints(self, session_id: Optional[str] = None) -> Dict:
        """List all breakpoints."""
        session_id = session_id or self.current_session
        if not session_id or session_id not in self.sessions:
            return {"error": "No active debug session"}
        
        session = self.sessions[session_id]
        return session.list_breakpoints()
    
    def inspect_file(self, filepath: str, start_line: int = 1, end_line: Optional[int] = None) -> Dict:
        """Show file content with line numbers for inspection."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            if end_line is None:
                end_line = min(start_line + 20, len(lines))  # Show 20 lines by default
            
            # Validate range
            start_line = max(1, start_line)
            end_line = min(end_line, len(lines))
            
            if start_line > len(lines):
                return {"error": f"Start line {start_line} exceeds file length {len(lines)}"}
            
            # Get breakpoints for this file
            session_id = self.current_session
            breakpoints = set()
            if session_id and session_id in self.sessions:
                breakpoints = set(self.sessions[session_id].breakpoints.keys())
            
            # Format with line numbers
            formatted_lines = []
            for i in range(start_line - 1, end_line):
                line_num = i + 1
                line_content = lines[i].rstrip()
                is_breakpoint = "🔴 " if line_num in breakpoints else "   "
                formatted_lines.append(f"{is_breakpoint}{line_num:4d} | {line_content}")
            
            return {
                "filepath": filepath,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": len(lines),
                "content": "\n".join(formatted_lines),
                "breakpoints": sorted(breakpoints)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def trace_execution(self, filepath: str, max_depth: int = 10) -> Dict:
        """Trace execution path of a file."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            # Read and parse file to find function/class definitions
            with open(file_path) as f:
                lines = f.readlines()
            
            functions = []
            classes = []
            
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("def "):
                    func_name = stripped.split("def ")[1].split("(")[0]
                    functions.append((func_name, i))
                elif stripped.startswith("class "):
                    class_name = stripped.split("class ")[1].split("(")[0].split(":")[0]
                    classes.append((class_name, i))
            
            return {
                "filepath": filepath,
                "functions": functions,
                "classes": classes,
                "total_functions": len(functions),
                "total_classes": len(classes),
                "message": f"Found {len(functions)} function(s) and {len(classes)} class(es)"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_function_details(self, filepath: str, function_name: str) -> Dict:
        """Get details about a specific function."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            # Find function definition
            func_line = None
            for i, line in enumerate(lines, 1):
                if f"def {function_name}(" in line:
                    func_line = i
                    break
            
            if func_line is None:
                return {"error": f"Function not found: {function_name}"}
            
            # Extract function signature and docstring
            sig_line = lines[func_line - 1].strip()
            
            # Simple docstring extraction
            docstring = ""
            if func_line < len(lines):
                next_line = lines[func_line].strip()
                if next_line.startswith(('"""', "'''")):
                    quote = next_line[:3]
                    for i in range(func_line, len(lines)):
                        if quote in lines[i] and i > func_line:
                            docstring = "".join(lines[func_line:i+1])
                            break
            
            # Find function body until next def
            body_lines = [sig_line]
            for i in range(func_line, len(lines)):
                if i > func_line - 1 and (lines[i].strip().startswith("def ") or 
                                         (lines[i].strip() and not lines[i].startswith(" "))):
                    break
                body_lines.append(lines[i].rstrip())
            
            return {
                "filepath": filepath,
                "function": function_name,
                "line": func_line,
                "signature": sig_line,
                "docstring": docstring,
                "body_lines": min(len(body_lines), 50),
                "has_docstring": bool(docstring)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_call_patterns(self, filepath: str) -> Dict:
        """Analyze function call patterns in a file."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                content = f.read()
            
            # Find function definitions
            import re
            func_pattern = r'def\s+(\w+)\s*\('
            functions = re.findall(func_pattern, content)
            
            # Find function calls (simple pattern)
            call_pattern = r'(\w+)\s*\('
            calls = re.findall(call_pattern, content)
            
            # Builtin functions to filter out
            builtins = {'print', 'len', 'range', 'str', 'int', 'list', 'dict', 'set',
                       'open', 'isinstance', 'hasattr', 'getattr', 'setattr'}
            
            internal_calls = [c for c in calls if c in functions and c not in builtins]
            external_calls = [c for c in calls if c not in functions and c not in builtins]
            
            return {
                "filepath": filepath,
                "functions_defined": functions,
                "internal_calls": list(set(internal_calls)),
                "external_calls": list(set(external_calls)),
                "message": f"{len(functions)} function(s), {len(set(internal_calls))} internal call(s), {len(set(external_calls))} external call(s)"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def end_session(self, session_id: Optional[str] = None) -> Dict:
        """End a debug session."""
        session_id = session_id or self.current_session
        if not session_id or session_id not in self.sessions:
            return {"error": "No active debug session"}
        
        del self.sessions[session_id]
        if self.current_session == session_id:
            self.current_session = None
        
        return {
            "status": "session_ended",
            "session_id": session_id,
            "message": f"Debug session ended"
        }


def format_debug_output(result: Dict) -> str:
    """Format debug output for display."""
    if "error" in result:
        return f"❌ Debug Error: {result['error']}"
    
    if "content" in result:
        # File inspection
        return f"""📖 {result['filepath']} (lines {result['start_line']}-{result['end_line']} of {result['total_lines']})

{result['content']}

🔴 Breakpoints: {', '.join(map(str, result['breakpoints'])) if result['breakpoints'] else 'None'}"""
    
    if "functions_defined" in result:
        # Call patterns
        return f"""📊 Call Pattern Analysis: {result['filepath']}

🔵 Functions Defined: {', '.join(result['functions_defined'])}
📤 Internal Calls: {', '.join(result['internal_calls']) if result['internal_calls'] else 'None'}
📥 External Calls: {', '.join(result['external_calls'][:10]) if result['external_calls'] else 'None'}

{result['message']}"""
    
    if "functions" in result:
        # Trace execution
        funcs = ", ".join([f"{name} (line {line})" for name, line in result['functions']]) if result['functions'] else "None"
        classes = ", ".join([f"{name} (line {line})" for name, line in result['classes']]) if result['classes'] else "None"
        
        return f"""🔍 Execution Trace: {result['filepath']}

🔵 Functions: {funcs}
📦 Classes: {classes}

{result['message']}"""
    
    if "signature" in result:
        # Function details
        return f"""📋 Function Details: {result['function']}

📄 File: {result['filepath']} (line {result['line']})
📝 Signature: {result['signature']}
📚 Has Docstring: {'✅ Yes' if result['has_docstring'] else '❌ No'}
📏 Lines: {result['body_lines']}"""
    
    # Default formatting
    status = result.get("status", "unknown")
    message = result.get("message", str(result))
    return f"🐛 Debugger: {message}"
