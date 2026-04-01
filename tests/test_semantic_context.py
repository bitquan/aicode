from src.tools.context_packer import pack_context
from src.tools.semantic_retriever import retrieve_relevant_snippets


def test_retrieve_relevant_snippets_scores_query(tmp_path):
    (tmp_path / "a.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def sub(a,b):\n    return a-b\n", encoding="utf-8")
    hits = retrieve_relevant_snippets(str(tmp_path), "add function", limit=2)
    assert hits
    assert hits[0]["path"] == "a.py"


def test_pack_context_limits_chars():
    snippets = [{"path": "a.py", "score": 2, "snippet": "x" * 5000}]
    packed = pack_context(snippets, max_chars=300)
    assert len(packed) <= 300
