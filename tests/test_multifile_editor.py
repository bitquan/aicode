from src.tools.multifile_editor import apply_multifile_rewrites


class StubAgent:
    def rewrite_file(self, file_path, instruction, current_content):
        return current_content + "# updated\n"


def test_apply_multifile_rewrites(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("y=1\n", encoding="utf-8")

    out = apply_multifile_rewrites(StubAgent(), str(tmp_path), ["src/a.py", "src/b.py"], "update")
    assert len(out["applied"]) == 2
    assert "updated" in (tmp_path / "src" / "a.py").read_text(encoding="utf-8")
