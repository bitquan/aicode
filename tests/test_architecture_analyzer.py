from src.tools.architecture_analyzer import ArchitectureAnalyzer


def test_analyze_structure(tmp_path):
    src = tmp_path / "src"
    (src / "agents").mkdir(parents=True)
    (src / "tools").mkdir(parents=True)
    (src / "server").mkdir(parents=True)

    (src / "main.py").write_text("import os\nfrom src.tools.x import y\n")
    (src / "agents" / "a.py").write_text("from src.tools.y import z\n")
    (src / "tools" / "x.py").write_text("import json\n")

    analyzer = ArchitectureAnalyzer(str(tmp_path))
    result = analyzer.analyze("src")

    assert result["python_files"] == 3
    assert "layers" in result
    assert "recommendations" in result


def test_analyze_missing_path(tmp_path):
    analyzer = ArchitectureAnalyzer(str(tmp_path))
    result = analyzer.analyze("missing")
    assert "error" in result
