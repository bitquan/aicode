"""Tests for APIGenerator."""
import pytest
from src.tools.api_generator import APIGenerator


@pytest.fixture()
def apigen(tmp_path):
    return APIGenerator(str(tmp_path))


def test_file_not_found(apigen):
    result = apigen.generate_from_file("not_there.py")
    assert "error" in result


def test_generates_routes_from_file(apigen, tmp_path):
    (tmp_path / "service.py").write_text(
        "def get_user(user_id: int):\n    pass\n\ndef create_user(name: str):\n    pass\n"
    )
    result = apigen.generate_from_file("service.py")
    assert result["route_count"] == 2
    assert "router" in result["router_header"]
    assert "get_user" in result["full_code"]
    assert "create_user" in result["full_code"]


def test_private_functions_excluded(apigen, tmp_path):
    (tmp_path / "priv.py").write_text(
        "def public_fn():\n    pass\n\ndef _private_fn():\n    pass\n"
    )
    result = apigen.generate_from_file("priv.py")
    assert result["route_count"] == 1


def test_generate_from_function(apigen):
    result = apigen.generate_from_function(
        "create_order",
        [{"name": "item_id", "type": "int"}, {"name": "qty", "type": "int"}],
        return_type="dict",
        http_method="POST",
    )
    assert result["method"] == "POST"
    assert "create_order" in result["code"]
    assert "/create-order" in result["endpoint"]


def test_route_uses_get_method(apigen, tmp_path):
    (tmp_path / "read.py").write_text("def list_items():\n    pass\n")
    result = apigen.generate_from_file("read.py", http_method="GET")
    assert "GET" in result["routes"][0]["method"] or "@router.get" in result["full_code"]
