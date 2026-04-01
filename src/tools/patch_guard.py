import re


def validate_unified_diff(diff_text: str) -> dict:
    lines = diff_text.splitlines()
    if not lines:
        return {"valid": False, "reason": "empty diff"}

    has_headers = any(line.startswith("--- ") for line in lines) and any(line.startswith("+++ ") for line in lines)
    has_hunk = any(line.startswith("@@") for line in lines)
    if not has_headers or not has_hunk:
        return {"valid": False, "reason": "missing unified diff headers or hunk"}

    dangerous = [line for line in lines if re.search(r"\b(rm\s+-rf|curl\s+|wget\s+|subprocess\.Popen)\b", line)]
    if dangerous:
        return {"valid": False, "reason": "dangerous patterns in patch"}

    return {"valid": True, "reason": "ok"}


def detect_patch_conflict(old_content: str, expected_fragment: str) -> bool:
    return expected_fragment not in old_content
