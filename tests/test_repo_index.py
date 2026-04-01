from src.tools.repo_index import build_file_index


def test_build_file_index_lists_expected_files(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("ok\n", encoding="utf-8")
    rows = build_file_index(str(tmp_path))
    paths = [row["path"] for row in rows]
    assert "a.py" in paths
    assert "b.txt" in paths
