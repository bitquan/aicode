from src.tools.circuit_breaker import should_trip_circuit_breaker


def test_circuit_breaker_repeated_category():
    attempts = [
        {"failure": {"category": "syntax", "summary": "a"}, "diff": "x"},
        {"failure": {"category": "syntax", "summary": "b"}, "diff": "y"},
    ]
    stop, reason = should_trip_circuit_breaker(attempts, min_repeats=2)
    assert stop is True
    assert "repeated failure category" in reason


def test_circuit_breaker_identical_summary():
    attempts = [
        {"failure": {"category": "runtime", "summary": "same"}, "diff": "x"},
        {"failure": {"category": "name", "summary": "same"}, "diff": "y"},
    ]
    stop, reason = should_trip_circuit_breaker(attempts, min_repeats=2)
    assert stop is True
    assert "summary" in reason
