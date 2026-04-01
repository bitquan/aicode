from src.tools.command_guard import validate_command
from src.tools.patch_guard import validate_unified_diff


def run_evaluation_suite() -> dict:
    checks = []

    checks.append(
        {
            "name": "command_guard_allows_pytest",
            "passed": validate_command("python -m pytest -q")["allowed"],
        }
    )
    checks.append(
        {
            "name": "command_guard_blocks_rm",
            "passed": not validate_command("python -m pytest -q && rm -rf /")["allowed"],
        }
    )
    checks.append(
        {
            "name": "patch_guard_accepts_unified",
            "passed": validate_unified_diff("--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n")["valid"],
        }
    )

    passed = sum(1 for item in checks if item["passed"])
    return {
        "total": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
