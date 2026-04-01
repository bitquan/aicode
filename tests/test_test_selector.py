from src.tools.test_selector import select_test_command


def test_select_test_for_src_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "demo.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    cmd = select_test_command(str(tmp_path), "src/demo.py")
    assert "tests/test_demo.py" in cmd


def test_select_default_when_no_targeted_test(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "other.py").write_text("x=1\n", encoding="utf-8")

    cmd = select_test_command(str(tmp_path), "src/other.py")
    assert cmd == "python -m pytest -q"
