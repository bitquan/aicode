from src.tools.fix_memory import retrieve_similar_fixes, store_fix_memory


def test_fix_memory_store_and_retrieve(tmp_path):
    store_fix_memory(str(tmp_path), {
        "target_path": "src/a.py",
        "failure_category": "syntax",
        "strategy": "syntax_patch",
        "success": True,
        "summary": "bad",
    })
    store_fix_memory(str(tmp_path), {
        "target_path": "src/a.py",
        "failure_category": "runtime",
        "strategy": "runtime_patch",
        "success": False,
        "summary": "boom",
    })

    rows = retrieve_similar_fixes(str(tmp_path), "src/a.py", "syntax", limit=2)
    assert rows
    assert rows[0]["failure_category"] == "syntax"
