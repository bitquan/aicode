from pathlib import Path

from src.tools.patch_applier import apply_file_edit, preview_diff


def test_preview_diff_contains_file_labels():
    diff = preview_diff("a\n", "b\n", "src/demo.py")
    assert "a/src/demo.py" in diff
    assert "b/src/demo.py" in diff


def test_apply_file_edit_writes_inside_workspace(tmp_path):
    workspace = tmp_path
    target = Path("src/example.py")
    result = apply_file_edit(str(workspace), str(target), "print('ok')\n")
    written = (workspace / target).read_text(encoding="utf-8")
    assert "print('ok')" in written
    assert result["diff"]


def test_apply_file_edit_blocks_path_escape(tmp_path):
    try:
        apply_file_edit(str(tmp_path), "../outside.py", "print('bad')\n")
        assert False, "Expected ValueError for path escape"
    except ValueError:
        assert True