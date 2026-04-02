"""Tests for interactive chat engine."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.tools.chat_engine import ChatEngine, MarkdownRenderer


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_parse_request_browse(mock_status, mock_index, mock_agent):
    """Test parsing browse commands."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    # Test various browse patterns
    request = engine.parse_request("browse src")
    assert request["action"] == "browse"
    assert "src" in request["path"]
    
    request = engine.parse_request("ls tests")
    assert request["action"] == "browse"
    
    request = engine.parse_request("show README.md")
    assert request["action"] == "browse"
    assert "readme" in request["path"].lower()
    assert mock_status.call_count == 1
    assert mock_status.call_args.kwargs == {"mode": "lightweight"}
    assert Path(mock_status.call_args.args[0]).resolve() == Path(".").resolve()


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_parse_request_other_actions(mock_status, mock_index, mock_agent):
    """Test parsing other request types."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    request = engine.parse_request("write hello world")
    assert request["action"] == "generate"
    
    request = engine.parse_request("fix src/main.py")
    assert request["action"] == "autofix"
    
    request = engine.parse_request("search foo")
    assert request["action"] == "search"

    request = engine.parse_request("Add a Clear Chat button to the VS Code panel")
    assert request["action"] == "research"
    
    request = engine.parse_request("status")
    assert request["action"] == "status"
    assert request["validation_mode"] == "lightweight"


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_parse_request_model_returns_typed_request(mock_status, mock_index, mock_agent):
    """The shared parser should surface typed requests for app surfaces."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine(".")
    request = engine.parse_request_model("status")

    assert request.action == "status"
    assert request.params["validation_mode"] == "lightweight"


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_execute_research_surfaces_candidate_files(mock_status, mock_index, mock_agent):
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine(".")
    snapshot = {
        'known_surfaces': {'vscode_panel': 'vscode-extension/src/extension.ts'},
        'server': {'reachable': True, 'url': 'http://127.0.0.1:8005'},
        'ollama': {'reachable': True, 'url': 'http://127.0.0.1:11434'},
        'web': {'enabled': True, 'summary': 'enabled (optional; explicit requests only)'},
        'commands': ['generate', 'research', 'status'],
    }

    with patch.object(engine, 'get_self_awareness_snapshot', return_value=snapshot), \
         patch('src.tools.commanding.handlers.repo.retrieve_relevant_snippets', return_value=[]):
        response = engine.execute({
            'action': 'research',
            'goal': 'Add a Clear Chat button to the VS Code panel',
        })

    assert 'Research Summary' in response
    assert 'vscode-extension/src/extension.ts' in response
    assert 'research → identify files → edit/apply change' in response


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_execute_browse_directory(mock_status, mock_index, mock_agent):
    """Test browsing a directory."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    request = {"action": "browse", "path": "."}
    response = engine.execute(request)
    
    # Should show directory listing
    assert "📁" in response or "📄" in response


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_execute_browse_nonexistent(mock_status, mock_index, mock_agent):
    """Test browsing a non-existent path."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    request = {"action": "browse", "path": "/nonexistent/impossible/path.txt"}
    response = engine.execute(request)
    
    # Should return error
    assert "❌" in response or "not found" in response.lower()


def test_markdown_renderer_code_blocks():
    """Test markdown rendering of code blocks."""
    text = """Here's some code:
```python
def hello():
    pass
```
That was code."""
    
    rendered = MarkdownRenderer.render(text)
    
    # Should contain formatting
    assert "hello" in rendered


def test_markdown_renderer_headers():
    """Test markdown rendering of headers."""
    text = """# Main Header
Some text
## Sub Header
More text."""
    
    rendered = MarkdownRenderer.render(text)
    
    # Should contain header text
    assert "Main Header" in rendered
    assert "Sub Header" in rendered


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_with_temp_files(mock_status, mock_index, mock_agent):
    """Test chat engine with actual temporary files."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create test file
        test_file = tmpdir_path / "test.txt"
        test_file.write_text("Hello, World!\nLine 2\nLine 3")
        
        # Create test subdir
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested content")
        
        # Test browse directory
        engine = ChatEngine(str(tmpdir_path))
        request = {"action": "browse", "path": "."}
        response = engine.execute(request)
        assert "test.txt" in response
        assert "subdir" in response
        
        # Test show file
        request = {"action": "browse", "path": "test.txt"}
        response = engine.execute(request)
        assert "Hello, World" in response
        assert "📄" in response


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_execute_unknown_action(mock_status, mock_index, mock_agent):
    """Test handling of unknown actions."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    request = {"action": "unknown_action"}
    response = engine.execute(request)
    
    # Should return helpful error with examples
    assert "❓" in response or "didn't understand" in response.lower()


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_parse_streaming_flags(mock_status, mock_index, mock_agent):
    """Test that streaming flags are set for long-running operations."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    engine = ChatEngine(".")
    
    # Generate should have streaming enabled
    request = engine.parse_request("write a function")
    assert request.get("stream") is True
    assert request["action"] == "generate"
    
    # Autofix should have streaming enabled
    request = engine.parse_request("fix src/main.py")
    assert request.get("stream") is True
    assert request["action"] == "autofix"
    
    # Browse should not have streaming
    request = engine.parse_request("browse src")
    assert request.get("stream") is None or request.get("stream") is False
    assert request["action"] == "browse"


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_generate_with_streaming(mock_status, mock_index, mock_agent):
    """Test code generation with streaming output enabled."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.generate_code.return_value = "def hello():\n    return 'world'"
    mock_agent_instance.evaluate_code.return_value = {"execution_ok": True, "stdout": "world"}
    
    mock_agent.return_value = mock_agent_instance
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    request = {"action": "generate", "instruction": "write hello function", "stream": True}
    response = engine.execute(request)
    
    # Should contain success indicator
    assert "✅" in response or "Success" in response


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_generate_without_streaming(mock_status, mock_index, mock_agent):
    """Test code generation with streaming disabled."""
    mock_agent_instance = MagicMock()
    mock_agent_instance.generate_code.return_value = "def hello():\n    return 'world'"
    mock_agent_instance.evaluate_code.return_value = {"execution_ok": True, "stdout": "world"}
    
    mock_agent.return_value = mock_agent_instance
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    request = {"action": "generate", "instruction": "write hello function", "stream": False}
    response = engine.execute(request)
    
    # Should still return a valid response
    assert response is not None
    assert len(response) > 0


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_debug_profile_coverage_handlers_are_methods(mock_status, mock_index, mock_agent):
    """Regression guard: handlers must be real ChatEngine methods."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine(".")

    assert callable(getattr(engine, "_handle_debug"))
    assert callable(getattr(engine, "_handle_profile"))
    assert callable(getattr(engine, "_handle_coverage"))


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_execute_dispatches_debug_profile_and_coverage(mock_status, mock_index, mock_agent):
    """Regression guard: execute() must dispatch to the specialized handlers."""
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}

    engine = ChatEngine(".")

    with patch.object(engine, "_handle_debug", return_value="debug-ok") as mock_debug:
        assert engine.execute({"action": "debug"}) == "debug-ok"
        mock_debug.assert_called_once_with({"action": "debug"})

    with patch.object(engine, "_handle_profile", return_value="profile-ok") as mock_profile:
        assert engine.execute({"action": "profile"}) == "profile-ok"
        mock_profile.assert_called_once_with({"action": "profile"})

    with patch.object(engine, "_handle_coverage", return_value="coverage-ok") as mock_coverage:
        assert engine.execute({"action": "coverage"}) == "coverage-ok"
        mock_coverage.assert_called_once_with({"action": "coverage"})
