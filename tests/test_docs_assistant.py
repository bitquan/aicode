from src.tools.docs_assistant import build_doc_update


def test_build_doc_update_lists_changed_files(tmp_path):
    output = build_doc_update(str(tmp_path), changed_files=["src/main.py", "README.md"])
    assert "src/main.py" in output
    assert "README.md" in output
