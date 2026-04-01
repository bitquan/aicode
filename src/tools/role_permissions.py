"""Role-based permission checks for chat actions."""

from pathlib import Path
from typing import Any


_DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "read_only": {"search", "browse", "status", "dashboard", "team_kb_read", "audit_view"},
    "developer": {
        "search", "browse", "status", "dashboard", "edit", "generate", "review", "debug",
        "profile", "coverage", "team_kb_read", "team_kb_write", "audit_view",
    },
    "release_manager": {
        "search", "browse", "status", "dashboard", "edit", "generate", "review", "debug",
        "profile", "coverage", "git", "pr", "deploy", "team_kb_read", "team_kb_write", "audit_view",
    },
    "admin": {"*"},
}


class RolePermissions:
    """Minimal RBAC helper for action-level permission checks."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.user_roles: dict[str, str] = {}

    def assign_role(self, user: str, role: str) -> dict[str, Any]:
        """Assign a role to user."""
        normalized = role.strip().lower()
        if normalized not in _DEFAULT_ROLE_PERMISSIONS:
            return {"ok": False, "error": f"Unknown role: {role}"}
        self.user_roles[user] = normalized
        return {"ok": True, "user": user, "role": normalized}

    def get_role(self, user: str) -> str:
        """Get assigned role or default developer."""
        return self.user_roles.get(user, "developer")

    def is_allowed(self, action: str, role: str | None = None, user: str | None = None) -> bool:
        """Check if role/user may perform action."""
        resolved_role = role or (self.get_role(user) if user else "developer")
        permissions = _DEFAULT_ROLE_PERMISSIONS.get(resolved_role, set())
        if "*" in permissions:
            return True
        return action in permissions

    def explain(self, action: str, role: str | None = None, user: str | None = None) -> dict[str, Any]:
        """Explain authorization decision."""
        resolved_role = role or (self.get_role(user) if user else "developer")
        permissions = _DEFAULT_ROLE_PERMISSIONS.get(resolved_role, set())
        allowed = self.is_allowed(action, role=resolved_role)
        return {
            "action": action,
            "role": resolved_role,
            "allowed": allowed,
            "permissions": sorted(permissions),
        }

    def list_roles(self) -> dict[str, list[str]]:
        """Return available roles and permissions."""
        return {role: sorted(perms) for role, perms in _DEFAULT_ROLE_PERMISSIONS.items()}
