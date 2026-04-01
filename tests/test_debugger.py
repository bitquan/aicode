"""
Tests for Interactive Python Debugger
"""

import pytest
from pathlib import Path
from src.tools.debugger import PythonDebugger, DebugSession, format_debug_output


class TestDebugSession:
    """Test DebugSession functionality."""
    
    @pytest.fixture
    def debug_session(self, tmp_path):
        """Create a debug session with a test file."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("def hello():\n    print('hi')\n")
        return DebugSession(str(test_file), str(tmp_path))
    
    def test_initialization(self, debug_session):
        """Test DebugSession initialization."""
        assert debug_session.breakpoints == {}
        assert debug_session.current_line == 0
        assert debug_session.workspace_root.exists()
    
    def test_set_breakpoint(self, debug_session):
        """Test setting a breakpoint."""
        result = debug_session.set_breakpoint(5)
        assert result["status"] == "set"
        assert 5 in debug_session.breakpoints
    
    def test_clear_breakpoint(self, debug_session):
        """Test clearing a breakpoint."""
        debug_session.set_breakpoint(5)
        result = debug_session.clear_breakpoint(5)
        assert result["status"] == "cleared"
        assert 5 not in debug_session.breakpoints
    
    def test_clear_all_breakpoints(self, debug_session):
        """Test clearing all breakpoints."""
        debug_session.set_breakpoint(1)
        debug_session.set_breakpoint(5)
        debug_session.set_breakpoint(10)
        
        result = debug_session.clear_all_breakpoints()
        assert result["status"] == "cleared_all"
        assert result["count"] == 3
        assert len(debug_session.breakpoints) == 0
    
    def test_list_breakpoints(self, debug_session):
        """Test listing breakpoints."""
        debug_session.set_breakpoint(5)
        debug_session.set_breakpoint(10)
        
        result = debug_session.list_breakpoints()
        assert result["count"] == 2
        assert 5 in result["breakpoints"]
        assert 10 in result["breakpoints"]


class TestPythonDebugger:
    """Test PythonDebugger functionality."""
    
    @pytest.fixture
    def debugger(self, tmp_path):
        """Create a debugger with workspace."""
        test_file = tmp_path / "main.py"
        test_file.write_text("""
def add(a, b):
    '''Add two numbers.'''
    return a + b

def greet(name):
    return f"Hello, {name}!"

class Calculator:
    def multiply(self, x, y):
        return x * y
""")
        return PythonDebugger(str(tmp_path))
    
    def test_start_debug_session(self, debugger, tmp_path):
        """Test starting a debug session."""
        result = debugger.start_debug_session("main.py")
        assert "status" in result or "error" not in result
        assert result["total_lines"] > 0
    
    def test_set_breakpoint(self, debugger, tmp_path):
        """Test setting breakpoint in active session."""
        debugger.start_debug_session("main.py")
        result = debugger.set_breakpoint(5)
        assert result["status"] == "set"
    
    def test_inspect_file(self, debugger, tmp_path):
        """Test file inspection with line numbers."""
        debugger.start_debug_session("main.py")
        result = debugger.inspect_file("main.py", start_line=1, end_line=5)
        assert "content" in result
        assert result["start_line"] == 1
        assert "1 |" in result["content"]  # Check for line numbering
    
    def test_trace_execution(self, debugger):
        """Test execution tracing."""
        result = debugger.trace_execution("main.py")
        assert "functions" in result
        assert "classes" in result
        assert len(result["functions"]) > 0
        assert len(result["classes"]) > 0
    
    def test_get_function_details(self, debugger):
        """Test getting function details."""
        result = debugger.get_function_details("main.py", "add")
        assert result["function"] == "add"
        assert result["line"] > 0
        assert "signature" in result
    
    def test_analyze_call_patterns(self, debugger):
        """Test call pattern analysis."""
        result = debugger.analyze_call_patterns("main.py")
        assert "functions_defined" in result
        assert "internal_calls" in result
        assert "external_calls" in result
    
    def test_end_session(self, debugger, tmp_path):
        """Test ending a debug session."""
        debugger.start_debug_session("main.py")
        result = debugger.end_session()
        assert result["status"] == "session_ended"
    
    def test_file_not_found(self, debugger):
        """Test handling of missing file."""
        result = debugger.start_debug_session("nonexistent.py")
        assert "error" in result
    
    def test_multiple_sessions(self, debugger, tmp_path):
        """Test managing multiple debug sessions."""
        (tmp_path / "file1.py").write_text("def f1(): pass")
        (tmp_path / "file2.py").write_text("def f2(): pass")
        
        debugger.start_debug_session("file1.py")
        assert debugger.current_session == "file1.py"
        
        debugger.start_debug_session("file2.py")
        assert debugger.current_session == "file2.py"
        
        assert len(debugger.sessions) == 2


class TestFormatDebugOutput:
    """Test debug output formatting."""
    
    def test_format_error(self):
        """Test error formatting."""
        result = {"error": "File not found"}
        output = format_debug_output(result)
        assert "Error" in output
        assert "File not found" in output
    
    def test_format_file_inspection(self):
        """Test file inspection formatting."""
        result = {
            "filepath": "test.py",
            "start_line": 1,
            "end_line": 5,
            "total_lines": 10,
            "content": "1 | def foo():\n2 |     pass",
            "breakpoints": [2]
        }
        output = format_debug_output(result)
        assert "test.py" in output
        assert "1-5" in output
        assert "Breakpoints" in output
    
    def test_format_trace_execution(self):
        """Test trace execution formatting."""
        result = {
            "filepath": "test.py",
            "functions": [("func1", 5), ("func2", 10)],
            "classes": [("MyClass", 15)],
            "message": "Found 2 functions"
        }
        output = format_debug_output(result)
        assert "Execution Trace" in output
        assert "func1" in output
        assert "MyClass" in output
    
    def test_format_default(self):
        """Test default formatting."""
        result = {"status": "success", "message": "Operation complete"}
        output = format_debug_output(result)
        assert "Debugger" in output or "Operation complete" in output
