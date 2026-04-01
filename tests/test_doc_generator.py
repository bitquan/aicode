"""Tests for DocGenerator."""
import pytest
from src.tools.doc_generator import DocGenerator


@pytest.fixture()
def gen(tmp_path):
    return DocGenerator(str(tmp_path))


def test_file_not_found(gen):
    result = gen.generate_module_docs("nonexistent.py")
    assert "error" in result


def test_detects_undocumented_function(gen, tmp_path):
    (tmp_path / "funcs.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    result = gen.generate_module_docs("funcs.py")
    assert result["undocumented"] >= 1
    assert any(d["name"] == "add" for d in result["docstrings"])


def test_documented_function_not_flagged(gen, tmp_path):
    (tmp_path / "docs.py").write_text(
        'def add(a, b):\n    """Add two numbers."""\n    return a + b\n'
    )
    result = gen.generate_module_docs("docs.py")
    assert result["undocumented"] == 0


def test_detects_undocumented_class(gen, tmp_path):
    (tmp_path / "cls.py").write_text("class Foo:\n    pass\n")
    result = gen.generate_module_docs("cls.py")
    assert result["undocumented"] >= 1
    assert any(d["type"] == "class" for d in result["docstrings"])


def test_generate_readme_section(gen, tmp_path):
    (tmp_path / "utils.py").write_text(
        'def greet(name):\n    """Say hello."""\n    return f"Hi {name}"\n'
    )
    readme = gen.generate_readme_section("utils.py")
    assert "greet" in readme
    assert "##" in readme


def test_list_undocumented(gen, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("def a():\n    pass\ndef b():\n    pass\n")
    result = gen.list_undocumented(str(src))
    assert result["total_missing_docstrings"] >= 2
