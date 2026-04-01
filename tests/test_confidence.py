from src.tools.confidence import score_attempt_confidence


def test_confidence_success_high():
    assert score_attempt_confidence("syntax", 0, True, False) == 0.99


def test_confidence_bounds_and_bonus():
    score = score_attempt_confidence("syntax", 3, False, False)
    assert 0.7 <= score <= 0.95


def test_confidence_flaky_penalty():
    base = score_attempt_confidence("runtime", 0, False, False)
    flaky = score_attempt_confidence("runtime", 0, False, True)
    assert flaky < base
