"""Tests for DiffVisualization."""

from src.tools.diff_visualization import DiffVisualization


DIFF = """
diff --git a/a.py b/a.py
index 111..222 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 line1
-line2
+line2 changed
+line3
"""


def test_summarize_diff_counts(tmp_path):
    tool = DiffVisualization(str(tmp_path))
    result = tool.summarize_diff(DIFF)
    assert result["status"] == "OK"
    assert result["total_added"] == 2
    assert result["total_removed"] == 1


def test_summarize_diff_empty(tmp_path):
    tool = DiffVisualization(str(tmp_path))
    result = tool.summarize_diff("")
    assert result["status"] == "EMPTY"


def test_summarize_file_missing(tmp_path):
    tool = DiffVisualization(str(tmp_path))
    result = tool.summarize_file("changes.diff")
    assert "error" in result


def test_visual_bar_present(tmp_path):
    tool = DiffVisualization(str(tmp_path))
    result = tool.summarize_diff(DIFF)
    assert result["files"][0]["visual"]
