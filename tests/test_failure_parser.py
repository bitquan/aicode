from src.tools.failure_parser import classify_failure


def test_classify_syntax_failure():
    info = classify_failure("", "SyntaxError: invalid syntax", timed_out=False)
    assert info["category"] == "syntax"


def test_classify_dependency_failure():
    info = classify_failure("", "ModuleNotFoundError: No module named 'x'", timed_out=False)
    assert info["category"] == "dependency"


def test_classify_timeout_failure():
    info = classify_failure("", "", timed_out=True)
    assert info["category"] == "timeout"


def test_classify_flaky_failure():
    info = classify_failure("test flaky rerun happened", "", timed_out=False)
    assert info["category"] == "flaky"
    assert info["flaky"]["suspected"] is True


def test_extract_pytest_nodeids():
    out = "FAILED tests/test_demo.py::test_one - AssertionError"
    info = classify_failure(out, "", timed_out=False)
    assert "tests/test_demo.py::test_one" in info["pytest_nodeids"]
