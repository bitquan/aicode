"""Tests for ArchitectureDiagramUnderstanding."""

from src.tools.architecture_diagram_understanding import ArchitectureDiagramUnderstanding


def test_analyze_text_basic_graph(tmp_path):
    tool = ArchitectureDiagramUnderstanding(str(tmp_path))
    text = """graph TD
A-->B
B-->C
"""
    result = tool.analyze_text(text)
    assert result["status"] == "OK"
    assert result["node_count"] == 3
    assert result["edge_count"] == 2


def test_analyze_text_no_graph(tmp_path):
    tool = ArchitectureDiagramUnderstanding(str(tmp_path))
    result = tool.analyze_text("just notes")
    assert result["status"] == "NO_GRAPH"


def test_analyze_file_missing(tmp_path):
    tool = ArchitectureDiagramUnderstanding(str(tmp_path))
    result = tool.analyze_file("missing.mmd")
    assert "error" in result


def test_flow_summary_contains_edges(tmp_path):
    tool = ArchitectureDiagramUnderstanding(str(tmp_path))
    result = tool.analyze_text("A->B\nB->C")
    lines = tool.flow_summary(result)
    assert any("A -> B" in line for line in lines)
