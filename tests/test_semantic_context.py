from src.tools.context_packer import pack_context
from src.tools.semantic_retriever import retrieve_relevant_snippets


def test_retrieve_relevant_snippets_scores_query(tmp_path):
    (tmp_path / "a.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def sub(a,b):\n    return a-b\n", encoding="utf-8")
    hits = retrieve_relevant_snippets(str(tmp_path), "add function", limit=2)
    assert hits
    assert hits[0]["path"] == "a.py"


def test_retriever_prioritizes_requested_paths(tmp_path):
    (tmp_path / "target.py").write_text("def work():\n    return 1\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("def work():\n    return 2\n", encoding="utf-8")

    hits = retrieve_relevant_snippets(
        str(tmp_path),
        "work return",
        limit=2,
        prioritize_paths=["target.py"],
    )
    assert hits[0]["path"] == "target.py"
    assert hits[0]["score_detail"]["path"] > 0


def test_retriever_boosts_failure_category_hints(tmp_path):
    (tmp_path / "typed.py").write_text("from typing import List\n\ndef f(x: int) -> int:\n    return x\n", encoding="utf-8")
    (tmp_path / "plain.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    hits = retrieve_relevant_snippets(
        str(tmp_path),
        "f return",
        limit=2,
        failure_category="type",
    )
    assert hits[0]["path"] == "typed.py"
    assert hits[0]["score_detail"]["failure"] > 0


def test_pack_context_limits_chars():
    snippets = [{"path": "a.py", "score": 2, "snippet": "x" * 5000}]
    packed = pack_context(snippets, max_chars=300)
    assert len(packed) <= 300
