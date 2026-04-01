def check_action_approval(action: str, role: str, auto_apply_requested: bool) -> dict:
    role = role.lower().strip() or "developer"
    privileged = {"owner", "maintainer", "admin"}

    if action == "edit" and auto_apply_requested and role not in privileged:
        return {
            "allowed": False,
            "reason": "auto-apply requires owner/maintainer/admin role",
        }

    return {"allowed": True, "reason": "ok"}
