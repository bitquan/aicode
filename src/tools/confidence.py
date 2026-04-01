def score_attempt_confidence(failure_category: str, similar_fix_count: int, test_success: bool, flaky_suspected: bool) -> float:
    if test_success:
        return 0.99

    base = {
        "syntax": 0.72,
        "name": 0.68,
        "type": 0.64,
        "dependency": 0.58,
        "assertion": 0.52,
        "runtime": 0.5,
        "timeout": 0.42,
        "flaky": 0.4,
        "unknown": 0.35,
    }.get(failure_category, 0.35)

    bonus = min(similar_fix_count * 0.05, 0.2)
    penalty = 0.1 if flaky_suspected else 0.0
    score = base + bonus - penalty
    return max(0.01, min(0.95, round(score, 2)))
