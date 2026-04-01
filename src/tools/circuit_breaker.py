import hashlib


def should_trip_circuit_breaker(attempts: list[dict], min_repeats: int = 2) -> tuple[bool, str]:
    if len(attempts) < min_repeats:
        return False, ""

    recent = attempts[-min_repeats:]
    categories = [a.get("failure", {}).get("category", "unknown") for a in recent]
    if len(set(categories)) == 1:
        return True, f"repeated failure category '{categories[0]}'"

    summaries = [a.get("failure", {}).get("summary", "") for a in recent]
    if all(summary and summary == summaries[0] for summary in summaries):
        return True, "repeated identical failure summary"

    diff_fingerprints = [_diff_fingerprint(a.get("diff", "")) for a in recent]
    if all(fp and fp == diff_fingerprints[0] for fp in diff_fingerprints):
        return True, "repeated identical patch fingerprint"

    return False, ""


def _diff_fingerprint(diff_text: str) -> str:
    if not diff_text:
        return ""
    return hashlib.sha1(diff_text.encode("utf-8")).hexdigest()[:12]
