"""Tests for self-building and self-improvement system."""

from pathlib import Path
from unittest.mock import patch, MagicMock
from src.tools.self_builder import SelfBuilder


def test_self_builder_initialization():
    """Test SelfBuilder initialization."""
    builder = SelfBuilder(".")
    
    assert builder.workspace_root == Path(".")
    assert builder.kb_dir.exists()
    assert isinstance(builder.patterns, dict)
    assert isinstance(builder.solutions, dict)


def test_analyze_interactions_empty():
    """Test analyzing empty interaction logs."""
    builder = SelfBuilder(".")
    
    result = builder.analyze_interactions([])
    
    assert result["total_interactions"] == 0
    assert result["success_rate"] == 0.0


def test_analyze_interactions_with_data():
    """Test analyzing interactions with success/failure data."""
    builder = SelfBuilder(".")
    
    logs = [
        {"query": "write function", "action": "generate", "success": True},
        {"query": "fix bug", "action": "autofix", "success": True},
        {"query": "search code", "action": "search", "success": False},
    ]
    
    result = builder.analyze_interactions(logs)
    
    assert result["total_interactions"] == 3
    assert result["success_rate"] == 2/3
    assert "generate" in result["action_breakdown"]
    assert "autofix" in result["action_breakdown"]
    assert len(result["successful_patterns"]) == 2
    assert len(result["failed_patterns"]) == 1


def test_generate_recommendations():
    """Test recommendation generation based on analysis."""
    builder = SelfBuilder(".")
    
    low_success_analysis = {
        "success_rate": 0.5,
        "successful_patterns": [],
        "failed_patterns": [{"query": "q1"}, {"query": "q2"}],
        "action_breakdown": {"search": 2}
    }
    
    recommendations = builder._generate_recommendations(low_success_analysis)
    
    assert any("success_rate" in r for r in recommendations)


def test_extract_solutions():
    """Test extracting reusable solutions from logs."""
    builder = SelfBuilder(".")
    
    logs = [
        {"query": "write http client", "action": "generate", "success": True},
        {"query": "fix bugs in main.py", "action": "autofix", "success": True},
        {"query": "find pattern", "action": "search", "success": True},
    ]
    
    solutions = builder.extract_solutions(logs)
    
    assert len(solutions) > 0
    assert any("code_generation" in k for k in solutions.keys())
    assert any("autofix" in k for k in solutions.keys())


def test_build_strategies():
    """Test building strategies from analysis."""
    builder = SelfBuilder(".")
    
    analysis = {
        "action_breakdown": {"generate": 10, "autofix": 5, "search": 3},
        "successful_patterns": [
            {"action": "generate"},
            {"action": "generate"},
            {"action": "autofix"},
        ],
    }
    
    strategies = builder.build_strategies(analysis)
    
    assert len(strategies) > 0
    assert any("optimize" in k for k in strategies.keys())


def test_learn_from_logs():
    """Test learning from interaction logs."""
    builder = SelfBuilder(".")
    
    logs = [
        {"query": "test query", "action": "generate", "success": True},
    ]
    
    builder.learn_from_logs(logs)
    
    # Should save data
    assert builder.patterns.get("total_learned_from") == 1
    assert builder.metrics.get("interaction_count") == 1


def test_get_improvement_suggestions():
    """Test getting improvement suggestions."""
    builder = SelfBuilder(".")
    builder.metrics["success_rate"] = 0.6
    
    suggestions = builder.get_improvement_suggestions()
    
    assert len(suggestions) > 0
    # Low success rate should trigger suggestions
    assert any("success" in s.lower() or "improve" in s.lower() for s in suggestions)


def test_export_knowledge_base():
    """Test exporting complete knowledge base."""
    builder = SelfBuilder(".")
    builder.patterns["test"] = "value"
    builder.solutions["sol1"] = "solution"
    
    kb = builder.export_knowledge_base()
    
    assert kb["patterns"]["test"] == "value"
    assert kb["solutions"]["sol1"] == "solution"
    assert "export_date" in kb


def test_generate_self_improvement_plan():
    """Test generating self-improvement plan."""
    builder = SelfBuilder(".")
    
    logs = [
        {"query": "q1", "action": "generate", "success": True},
        {"query": "q2", "action": "generate", "success": False},
    ]
    
    plan = builder.generate_self_improvement_plan(logs)
    
    assert plan["status"] == "ready"
    assert plan["current_success_rate"] == 0.5  # 1 success, 1 failure
    assert plan["target_success_rate"] == 0.95
    assert plan["estimated_cycles"] > 0
    assert len(plan["actions"]) > 0


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_learn_action(mock_status, mock_index, mock_agent):
    """Test chat engine learn action."""
    from src.tools.chat_engine import ChatEngine
    
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    
    # Add some interactions
    engine._log_interaction("write func", "generate", True, "docs")
    engine._log_interaction("fix bug", "autofix", True, "docs")
    
    request = {"action": "learn"}
    response = engine._handle_learn(request)
    
    # Should contain learning results
    assert "Self-Improvement" in response
    assert "Success Rate" in response


@patch('src.tools.chat_engine.CodingAgent')
@patch('src.tools.chat_engine.build_file_index')
@patch('src.tools.chat_engine.build_status_report')
def test_chat_engine_parse_learn_request(mock_status, mock_index, mock_agent):
    """Test parsing learn commands."""
    from src.tools.chat_engine import ChatEngine
    
    mock_agent.return_value = MagicMock()
    mock_index.return_value = {}
    mock_status.return_value = {}
    
    engine = ChatEngine(".")
    
    # Test various learn patterns
    request = engine.parse_request("learn")
    assert request["action"] == "learn"
    
    request = engine.parse_request("improve myself")
    assert request["action"] == "learn"
    
    request = engine.parse_request("self-improve")
    assert request["action"] == "learn"
    
    request = engine.parse_request("build myself")
    assert request["action"] == "learn"


def test_self_builder_cache_persistence():
    """Test that learned knowledge persists across instances."""
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # First instance learns
        builder1 = SelfBuilder(tmpdir)
        logs = [{"query": "test", "action": "generate", "success": True}]
        builder1.learn_from_logs(logs)
        
        # Second instance should load same knowledge
        builder2 = SelfBuilder(tmpdir)
        assert builder2.patterns.get("total_learned_from") == 1


def test_code_template_building():
    """Test building code templates from patterns."""
    builder = SelfBuilder(".")
    
    logs = [
        {"query": "make http request", "action": "generate", "success": True},
        {"query": "filter and sort list", "action": "generate", "success": True},
    ]
    
    templates = builder.build_code_templates(logs)
    
    assert "http_client" in templates
    assert "data_transform" in templates
