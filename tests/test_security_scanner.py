"""Tests for SecurityScanner."""
import pytest
from src.tools.security_scanner import SecurityScanner


@pytest.fixture()
def scanner(tmp_path):
    return SecurityScanner(str(tmp_path))


def test_scan_file_not_found(scanner):
    result = scanner.scan_file("nonexistent.py")
    assert "error" in result or result["total"] == 0


def test_scan_clean_file(scanner, tmp_path):
    f = tmp_path / "clean.py"
    f.write_text("def add(a, b):\n    return a + b\n")
    result = scanner.scan_file("clean.py")
    assert result["total"] == 0


def test_detects_hardcoded_password(scanner, tmp_path):
    f = tmp_path / "bad.py"
    f.write_text('password = "s3cr3t"\n')
    result = scanner.scan_file("bad.py")
    assert result["total"] >= 1
    assert any(f["rule_id"] == "SEC001" for f in result["findings"])


def test_detects_eval_usage(scanner, tmp_path):
    f = tmp_path / "eval_bad.py"
    f.write_text('result = eval(user_input)\n')
    result = scanner.scan_file("eval_bad.py")
    assert any(f["rule_id"] == "SEC008" for f in result["findings"])


def test_detects_pickle_loads(scanner, tmp_path):
    f = tmp_path / "pickle_bad.py"
    f.write_text("import pickle\ndata = pickle.loads(raw)\n")
    result = scanner.scan_file("pickle_bad.py")
    assert any(f["rule_id"] == "SEC004" for f in result["findings"])


def test_scan_directory_returns_summary(scanner, tmp_path):
    (tmp_path / "a.py").write_text('secret = "abc123"\n')
    (tmp_path / "b.py").write_text("x = 1 + 1\n")
    result = scanner.scan_directory(str(tmp_path))
    assert result["scanned_files"] >= 1
    assert "total_findings" in result


def test_suggest_fixes(scanner, tmp_path):
    f = tmp_path / "s.py"
    f.write_text('api_key = "supersecret"\nresult = eval("1+1")\n')
    result = scanner.scan_file("s.py")
    fixes = scanner.suggest_fixes(result["findings"])
    assert len(fixes) >= 1
    assert any("SEC001" in fix or "SEC008" in fix for fix in fixes)
