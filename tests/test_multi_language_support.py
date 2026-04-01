"""Tests for MultiLanguageSupport."""

from src.tools.multi_language_support import MultiLanguageSupport


def test_detect_language_python(tmp_path):
    tool = MultiLanguageSupport(str(tmp_path))
    result = tool.detect_language("src/main.py")
    assert result["language"] == "python"


def test_detect_language_unknown(tmp_path):
    tool = MultiLanguageSupport(str(tmp_path))
    result = tool.detect_language("README.custom")
    assert result["language"] == "unknown"


def test_language_summary_counts(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hi')")
    (src / "app.ts").write_text("export const x = 1")
    (src / "lib.go").write_text("package main")

    tool = MultiLanguageSupport(str(tmp_path))
    summary = tool.language_summary("src/")
    assert summary["scanned_files"] == 3
    assert any(item["language"] == "python" for item in summary["languages"])


def test_language_summary_missing_target(tmp_path):
    tool = MultiLanguageSupport(str(tmp_path))
    result = tool.language_summary("missing/")
    assert "error" in result


def test_starter_snippet(tmp_path):
    tool = MultiLanguageSupport(str(tmp_path))
    result = tool.starter_snippet("rust")
    assert "fn hello" in result["snippet"]
