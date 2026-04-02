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
        "def get_user(user_id: int):\n    return {'id': user_id}\n\n"
        "def create_user(name: str):\n    return {'name': name}\n"
    )
    result = apigen.generate_from_file("service.py")
    assert result["route_count"] == 2
    assert "router" in result["router_header"]
    assert "get_user" in result["full_code"]
    assert "create_user" in result["full_code"]
    assert "NotImplementedError" not in result["full_code"]


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
    assert "NotImplementedError" not in result["code"]


def test_route_uses_get_method(apigen, tmp_path):
    (tmp_path / "read.py").write_text("def list_items():\n    pass\n")
    result = apigen.generate_from_file("read.py", http_method="GET")
    assert "GET" in result["routes"][0]["method"] or "@router.get" in result["full_code"]


def test_mock_mode_uses_mock_response(apigen, tmp_path):
    (tmp_path / "mockable.py").write_text("def list_items():\n    return ['a']\n")
    result = apigen.generate_from_file("mockable.py", generation_mode="mock")
    assert result["generation_mode"] == "mock"
    assert "return _mock_response" in result["full_code"]


def test_stub_mode_uses_http_501(apigen, tmp_path):
    (tmp_path / "stubby.py").write_text("def list_items():\n    return ['a']\n")
    result = apigen.generate_from_file("stubby.py", generation_mode="stub")
    assert result["generation_mode"] == "stub"
    assert "status_code=501" in result["full_code"]


def test_passthrough_mode_invokes_impl(apigen, tmp_path):
    (tmp_path / "service.py").write_text("def list_items():\n    return ['a']\n")
    result = apigen.generate_from_file("service.py", generation_mode="passthrough")
    assert result["generation_mode"] == "passthrough"
    assert "return _invoke_impl" in result["full_code"]


def test_invalid_generation_mode_returns_error(apigen, tmp_path):
    (tmp_path / "service.py").write_text("def list_items():\n    return ['a']\n")
    result = apigen.generate_from_file("service.py", generation_mode="invalid")
    assert "error" in result
    assert result["routes"] == []


def test_invalid_http_method_returns_error(apigen, tmp_path):
    (tmp_path / "service.py").write_text("def list_items():\n    return ['a']\n")
    result = apigen.generate_from_file("service.py", http_method="TRACE")
    assert "error" in result
    assert result["routes"] == []
