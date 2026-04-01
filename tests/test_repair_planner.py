from src.tools.repair_planner import plan_repair_files


def test_plan_repair_files_includes_target_and_test(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "demo.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    files = plan_repair_files(str(tmp_path), "src/demo.py", {"raw": ""})
    assert "src/demo.py" in files
    assert "tests/test_demo.py" in files


def test_plan_repair_files_includes_traceback_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "helper.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "src" / "main.py").write_text("x=1\n", encoding="utf-8")

    raw = 'Traceback\nFile "src/helper.py", line 1, in <module>'
    files = plan_repair_files(str(tmp_path), "src/main.py", {"raw": raw})
    assert "src/helper.py" in files
