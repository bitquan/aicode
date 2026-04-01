"""Tests for prompt taxonomy baseline map."""

from src.tools.prompt_taxonomy import TOP_20_INTENT_TAXONOMY, classify_prompt_type


def test_taxonomy_has_20_intents():
    assert len(TOP_20_INTENT_TAXONOMY) == 20


def test_classify_repo_summary():
    result = classify_prompt_type("what can you tell me about this repo?")
    assert result["intent"] == "repo_summary"


def test_classify_unknown():
    result = classify_prompt_type("totally unmatched phrase")
    assert result["intent"] == "unknown"
