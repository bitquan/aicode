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
    
    request = engine.parse_request("status")
    assert request["action"] == "status"


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
