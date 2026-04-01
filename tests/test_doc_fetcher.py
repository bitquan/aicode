"""Tests for documentation fetching and context enhancement."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from src.tools.doc_fetcher import DocFetcher, enhance_with_docs


def test_doc_fetcher_initialization():
    """Test doc fetcher initialization."""
    fetcher = DocFetcher(".")
    assert fetcher.cache_dir.exists()
    assert fetcher.cache_ttl_hours == 72


def test_doc_fetcher_get_intelligent_summary():
    """Test getting intelligent summaries for packages."""
    fetcher = DocFetcher(".")
    
    summary = fetcher._get_intelligent_summary("requests")
    assert "HTTP" in summary
    assert "requests.get" in summary
    
    summary = fetcher._get_intelligent_summary("fastapi")
    assert "API" in summary or "web" in summary.lower()
    
    summary = fetcher._get_intelligent_summary("pytest")
    assert "test" in summary.lower()


def test_doc_fetcher_index_library():
    """Test indexing library documentation."""
    fetcher = DocFetcher(".")
    
    results = fetcher.index_library(["requests", "fastapi"])
    
    assert "requests" in results
    assert "fastapi" in results
    assert len(results["requests"]) > 0
    assert len(results["fastapi"]) > 0


def test_doc_fetcher_get_relevant_docs():
    """Test retrieving relevant documentation."""
    fetcher = DocFetcher(".")
    
    docs = fetcher.get_relevant_docs("make HTTP request", ["requests", "fastapi"])
    
    # Should find requests as relevant
    result_text = "\n".join(docs)
    assert len(docs) > 0


def test_doc_fetcher_extract_requirements_pyproject():
    """Test extracting package names from pyproject.toml."""
    fetcher = DocFetcher(".")
    
    packages = fetcher.extract_requirements("pyproject.toml")
    
    # Should find some packages
    assert isinstance(packages, list)
    # Note: actual packages depend on project configuration


def test_enhance_with_docs():
    """Test enhancement function."""
    result = enhance_with_docs(".", "create HTTP request")
    
    # Should return some documentation or empty string, not error
    assert isinstance(result, str)


def test_doc_fetcher_cache_freshness():
    """Test cache freshness checking."""
    fetcher = DocFetcher(".")
    
    # New cache should be considered fresh
    fetcher.doc_cache["test_pkg"] = {
        "summary": "test summary",
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }
    
    assert fetcher._is_cache_fresh("test_pkg") is True


def test_doc_fetcher_stale_cache():
    """Test detection of stale cache."""
    fetcher = DocFetcher(".")
    from datetime import datetime, timedelta
    
    # Add old timestamp (older than cache TTL)
    old_time = (datetime.now() - timedelta(hours=100)).isoformat()
    fetcher.doc_cache["old_pkg"] = {
        "summary": "old summary",
        "timestamp": old_time
    }
    
    assert fetcher._is_cache_fresh("old_pkg") is False


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_with_doc_context(mock_status, mock_index, mock_agent):
    """Test chat engine initializes with doc fetcher."""
    from src.tools.chat_engine import ChatEngine
    
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    
    # Should have doc fetcher initialized
    assert hasattr(engine, 'doc_fetcher')
    assert isinstance(engine.doc_fetcher, DocFetcher)
    
    # Should have interaction log
    assert hasattr(engine, 'interaction_log')
    assert isinstance(engine.interaction_log, list)


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_logs_interactions(mock_status, mock_index, mock_agent):
    """Test that chat engine logs interactions for learning."""
    from src.tools.chat_engine import ChatEngine
    
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    engine._log_interaction("write code", "generate", True, "doc context")
    
    assert len(engine.interaction_log) == 1
    assert engine.interaction_log[0]["action"] == "generate"
    assert engine.interaction_log[0]["success"] is True
    assert "write code" in engine.interaction_log[0]["query"]
