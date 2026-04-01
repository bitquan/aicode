"""Tests for TeamKnowledgeBase."""

from src.tools.team_knowledge_base import TeamKnowledgeBase


def test_add_and_load_entries(tmp_path):
    kb = TeamKnowledgeBase(str(tmp_path))
    kb.add_entry(topic="auth", note="Use token expiry checks", author="alice", tags=["security"])
    entries = kb.load_entries()
    assert len(entries) == 1
    assert entries[0]["topic"] == "auth"


def test_search_matches_topic_and_note(tmp_path):
    kb = TeamKnowledgeBase(str(tmp_path))
    kb.add_entry(topic="api", note="Document all endpoints", author="bob")
    kb.add_entry(topic="security", note="Rotate secrets", author="alice")
    result = kb.search("secret")
    assert result["count"] == 1
    assert result["entries"][0]["topic"] == "security"


def test_recent_limit(tmp_path):
    kb = TeamKnowledgeBase(str(tmp_path))
    for i in range(5):
        kb.add_entry(topic=f"t{i}", note=f"n{i}")
    recent = kb.recent(limit=3)
    assert recent["count"] == 3


def test_stats_top_topics(tmp_path):
    kb = TeamKnowledgeBase(str(tmp_path))
    kb.add_entry(topic="auth", note="a")
    kb.add_entry(topic="auth", note="b")
    kb.add_entry(topic="api", note="c")
    stats = kb.stats()
    assert stats["total_entries"] == 3
    assert stats["top_topics"][0]["topic"] == "auth"
