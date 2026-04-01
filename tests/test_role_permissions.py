"""Tests for RolePermissions."""

from src.tools.role_permissions import RolePermissions


def test_assign_and_get_role(tmp_path):
    rbac = RolePermissions(str(tmp_path))
    result = rbac.assign_role("alice", "read_only")
    assert result["ok"] is True
    assert rbac.get_role("alice") == "read_only"


def test_unknown_role_rejected(tmp_path):
    rbac = RolePermissions(str(tmp_path))
    result = rbac.assign_role("alice", "superuser")
    assert result["ok"] is False


def test_read_only_denies_edit(tmp_path):
    rbac = RolePermissions(str(tmp_path))
    rbac.assign_role("alice", "read_only")
    assert rbac.is_allowed("edit", user="alice") is False


def test_admin_allows_any_action(tmp_path):
    rbac = RolePermissions(str(tmp_path))
    rbac.assign_role("root", "admin")
    assert rbac.is_allowed("deploy", user="root") is True


def test_explain_payload(tmp_path):
    rbac = RolePermissions(str(tmp_path))
    data = rbac.explain("search", role="developer")
    assert data["action"] == "search"
    assert "permissions" in data
