from src.tools.approval_policy import check_action_approval


def test_approval_policy_blocks_auto_apply_for_developer():
    out = check_action_approval("edit", role="developer", auto_apply_requested=True)
    assert out["allowed"] is False


def test_approval_policy_allows_auto_apply_for_admin():
    out = check_action_approval("edit", role="admin", auto_apply_requested=True)
    assert out["allowed"] is True
