"""Tests for DependencyResolver."""
import pytest
from src.tools.dependency_resolver import DependencyResolver


@pytest.fixture()
def resolver(tmp_path):
    return DependencyResolver(str(tmp_path))


def test_no_dep_file(resolver):
    result = resolver.analyse()
    assert "error" in result


def test_parse_requirements_txt(resolver, tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "requests>=2.28\npytest\nfastapi>=0.100\n"
    )
    result = resolver.analyse()
    assert result["total_packages"] == 3
    assert result["health"] in ("GOOD", "NEEDS_ATTENTION")


def test_detects_upgrade_suggestion(resolver, tmp_path):
    (tmp_path / "requirements.txt").write_text("pydantic\ndjango\n")
    result = resolver.analyse()
    names = [u["package"] for u in result["upgrade_suggestions"]]
    assert any("pydantic" in n.lower() or "django" in n.lower() for n in names)


def test_no_conflicts_on_unique_deps(resolver, tmp_path):
    (tmp_path / "requirements.txt").write_text("requests\nflask\n")
    result = resolver.analyse()
    assert result["conflicts"] == []


def test_suggest_pinned_versions(resolver):
    deps = [{"name": "pydantic", "spec": ""}, {"name": "requests", "spec": ">=2.0"}]
    pinned = resolver.suggest_pinned_versions(deps)
    assert len(pinned) == 2
    assert any("pydantic" in p for p in pinned)


def test_analyse_file_not_found(resolver):
    result = resolver.analyse_file("no_such_file.txt")
    assert "error" in result
