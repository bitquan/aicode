from pathlib import Path

from src.tools.patch_applier import apply_file_edit
from src.tools.patch_guard import detect_patch_conflict, validate_unified_diff
from src.tools.snapshot_manager import rollback_snapshot


def test_validate_unified_diff_and_conflict():
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    assert validate_unified_diff(diff)["valid"] is True
    assert detect_patch_conflict("hello", "missing") is True


def test_apply_file_edit_creates_snapshot_and_rollback(tmp_path):
    path = tmp_path / "x.py"
    path.write_text("x=1\n", encoding="utf-8")
    result = apply_file_edit(str(tmp_path), "x.py", "x=2\n")
    assert result["snapshot"]
    rollback_snapshot(str(tmp_path), "x.py", result["snapshot"])
    assert path.read_text(encoding="utf-8") == "x=1\n"
