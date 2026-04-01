"""Tests for CustomLLMSupport."""

from src.tools.custom_llm_support import CustomLLMSupport


def test_default_routes_present(tmp_path):
    router = CustomLLMSupport(str(tmp_path))
    models = router.list_models()
    assert models["count"] >= 3


def test_classify_code_task(tmp_path):
    router = CustomLLMSupport(str(tmp_path))
    assert router.classify_task("implement auth middleware") == "code"


def test_classify_review_task(tmp_path):
    router = CustomLLMSupport(str(tmp_path))
    assert router.classify_task("security audit this patch") == "review"


def test_register_and_choose_model(tmp_path):
    router = CustomLLMSupport(str(tmp_path))
    router.register_model("review", "anthropic", "claude-sonnet", "medium")
    chosen = router.choose_model("review security report")
    assert chosen["provider"] == "anthropic"
    assert chosen["model"] == "claude-sonnet"
