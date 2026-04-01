from src.tools.project_memory import get_notes, remember_note, search_notes


def test_project_memory_add_get_search(tmp_path):
    remember_note(str(tmp_path), key="style", value="use pytest")
    remember_note(str(tmp_path), key="workflow", value="run autofix first")

    rows = get_notes(str(tmp_path), key="style")
    assert len(rows) == 1
    assert rows[0]["value"] == "use pytest"

    hits = search_notes(str(tmp_path), "autofix")
    assert hits
    assert hits[0]["key"] == "workflow"
