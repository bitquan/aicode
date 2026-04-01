"""Tests for FrameworkExperts."""

from src.tools.framework_experts import FrameworkExperts


def test_detect_frameworks_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("fastapi = \"*\"\ndjango = \"*\"")
    experts = FrameworkExperts(str(tmp_path))
    result = experts.detect_frameworks()
    assert result["count"] >= 1
    assert "fastapi" in result["frameworks"]


def test_expert_advice_supported(tmp_path):
    experts = FrameworkExperts(str(tmp_path))
    result = experts.expert_advice("fastapi", "security best practices")
    assert result["framework"] == "fastapi"
    assert result["focus"] == "security"
    assert len(result["tips"]) >= 1


def test_expert_advice_unsupported(tmp_path):
    experts = FrameworkExperts(str(tmp_path))
    result = experts.expert_advice("spring", "auth")
    assert "error" in result


def test_recommend_expert_from_task(tmp_path):
    experts = FrameworkExperts(str(tmp_path))
    result = experts.recommend_expert("need django migration help")
    assert result["framework"] == "django"


def test_recommend_expert_from_detected_repo(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\n")
    experts = FrameworkExperts(str(tmp_path))
    result = experts.recommend_expert("how should I structure routes")
    assert result["framework"] == "flask"
