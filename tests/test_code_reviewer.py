"""
Tests for Code Review Assistant
"""

import pytest
from pathlib import Path
from src.tools.code_reviewer import CodeReviewer, ReviewIssue, format_review_report


class TestCodeReviewer:
    """Test CodeReviewer functionality."""
    
    @pytest.fixture
    def reviewer(self, tmp_path):
        """Create a reviewer with temporary workspace."""
        return CodeReviewer(str(tmp_path))
    
    def test_initialization(self, reviewer):
        """Test CodeReviewer initialization."""
        assert reviewer.workspace_root.exists()
        assert reviewer.issues == []
    
    def test_security_sql_injection(self, reviewer, tmp_path):
        """Test SQL injection detection."""
        test_file = tmp_path / "bad_sql.py"
        test_file.write_text("""
def query_user(user_id):
    sql = f"SELECT * FROM users WHERE id = {user_id}"
    execute(sql)
""")
        
        report = reviewer.review_file("bad_sql.py")
        assert report["quality_score"] < 100
        assert any("SQL injection" in issue["message"] for issue in report["issues"])
    
    def test_security_hard_coded_credentials(self, reviewer, tmp_path):
        """Test hard-coded credentials detection."""
        test_file = tmp_path / "secrets.py"
        test_file.write_text("""
API_KEY = "sk-1234567890abcdef"
PASSWORD = "super_secret_password_123"
""")
        
        report = reviewer.review_file("secrets.py")
        assert any("credentials" in issue["message"].lower() for issue in report["issues"])
    
    def test_security_eval(self, reviewer, tmp_path):
        """Test eval/exec detection."""
        test_file = tmp_path / "unsafe.py"
        test_file.write_text("""
user_input = input()
eval(user_input)
""")
        
        report = reviewer.review_file("unsafe.py")
        assert any("eval" in issue["message"].lower() for issue in report["issues"])
    
    def test_security_pickle(self, reviewer, tmp_path):
        """Test pickle detection."""
        test_file = tmp_path / "unsafe_pickle.py"
        test_file.write_text("""
import pickle
data = pickle.load(open("data.pkl"))
""")
        
        report = reviewer.review_file("unsafe_pickle.py")
        assert any("pickle" in issue["message"].lower() for issue in report["issues"])
    
    def test_style_long_lines(self, reviewer, tmp_path):
        """Test long line detection."""
        test_file = tmp_path / "long_lines.py"
        test_file.write_text("""
def function_with_very_long_line():
    result = "This is an extremely long line that exceeds 100 characters and should be flagged by the reviewer for being too long"
""")
        
        report = reviewer.review_file("long_lines.py")
        assert any("Line too long" in issue["message"] for issue in report["issues"])
    
    def test_style_trailing_whitespace(self, reviewer, tmp_path):
        """Test trailing whitespace detection."""
        test_file = tmp_path / "trailing.py"
        test_file.write_text("def foo():  \n    pass")
        
        report = reviewer.review_file("trailing.py")
        assert any("Trailing whitespace" in issue["message"] for issue in report["issues"])
    
    def test_complexity_deep_nesting(self, reviewer, tmp_path):
        """Test deep nesting detection."""
        test_file = tmp_path / "nested.py"
        test_file.write_text("""
def deeply_nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            pass
""")
        
        report = reviewer.review_file("nested.py")
        # Should detect deep nesting
        assert report["quality_score"] < 100
    
    def test_best_practice_bare_except(self, reviewer, tmp_path):
        """Test bare except detection."""
        test_file = tmp_path / "bare_except.py"
        test_file.write_text("""
try:
    dangerous_operation()
except:
    print("Error occurred")
""")
        
        report = reviewer.review_file("bare_except.py")
        assert any("except" in issue["message"].lower() for issue in report["issues"])
    
    def test_best_practice_star_imports(self, reviewer, tmp_path):
        """Test star import detection."""
        test_file = tmp_path / "star_import.py"
        test_file.write_text("""
from module import *
from another_module import *
""")
        
        report = reviewer.review_file("star_import.py")
        assert any("Star import" in issue["message"] or "import *" in issue["message"] 
                  for issue in report["issues"])
    
    def test_best_practice_global(self, reviewer, tmp_path):
        """Test global variable detection."""
        test_file = tmp_path / "global_var.py"
        test_file.write_text("""
counter = 0

def increment():
    global counter
    counter += 1
""")
        
        report = reviewer.review_file("global_var.py")
        assert any("global" in issue["message"].lower() for issue in report["issues"])
    
    def test_documentation_missing_module_docstring(self, reviewer, tmp_path):
        """Test missing module docstring detection."""
        test_file = tmp_path / "no_docstring.py"
        test_file.write_text("""
import os

def foo():
    pass
""")
        
        report = reviewer.review_file("no_docstring.py")
        assert any("docstring" in issue["message"].lower() for issue in report["issues"])
    
    def test_quality_score_calculation(self, reviewer, tmp_path):
        """Test quality score calculation."""
        test_file = tmp_path / "good_code.py"
        test_file.write_text("""
\"\"\"Good code example.\"\"\"

def hello():
    \"\"\"Say hello.\"\"\"
    return "Hello, World!"
""")
        
        report = reviewer.review_file("good_code.py")
        assert report["quality_score"] >= 80  # Should be fairly good
    
    def test_issue_grouping_by_severity(self, reviewer, tmp_path):
        """Test issues are grouped by severity."""
        test_file = tmp_path / "multiple_issues.py"
        test_file.write_text("""
eval(input())
try:
    pass
except:
    pass
""")
        
        report = reviewer.review_file("multiple_issues.py")
        assert "by_severity" in report
        assert report["by_severity"]["critical"] > 0  # eval should be critical
    
    def test_issue_grouping_by_category(self, reviewer, tmp_path):
        """Test issues are grouped by category."""
        test_file = tmp_path / "category_test.py"
        test_file.write_text("""
eval(input())
API_KEY = "secret"
try:
    pass
except:
    pass
""")
        
        report = reviewer.review_file("category_test.py")
        assert "by_category" in report
        assert "security" in report["by_category"]
    
    def test_file_not_found(self, reviewer):
        """Test handling of non-existent file."""
        report = reviewer.review_file("nonexistent.py")
        assert "error" in report
    
    def test_codebase_review(self, reviewer, tmp_path):
        """Test full codebase review."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        
        (src_dir / "file1.py").write_text('"""File 1."""\neval(x)')
        (src_dir / "file2.py").write_text('"""File 2."""\npass')
        
        report = reviewer.review_codebase(include_patterns=["src/*.py"])
        assert "codebase_score" in report
        assert report["files_reviewed"] == 2
    
    def test_review_issue_dataclass(self):
        """Test ReviewIssue creation."""
        issue = ReviewIssue(
            severity="high",
            category="security",
            line=42,
            message="Test message",
            suggestion="Test suggestion"
        )
        assert issue.severity == "high"
        assert issue.line == 42


class TestFormatReviewReport:
    """Test report formatting."""
    
    def test_format_error_report(self):
        """Test formatting error report."""
        report = {"error": "File not found"}
        result = format_review_report(report)
        assert "Error" in result
    
    def test_format_clean_code(self):
        """Test formatting clean code report."""
        report = {
            "filepath": "good.py",
            "quality_score": 95,
            "total_issues": 0,
            "by_severity": {},
            "issues": []
        }
        result = format_review_report(report)
        assert "95/100" in result
        assert "good.py" in result
    
    def test_format_issues_display(self):
        """Test formatting displays issues."""
        report = {
            "filepath": "bad.py",
            "quality_score": 50,
            "total_issues": 2,
            "by_severity": {"critical": 1, "high": 1},
            "issues": [
                {
                    "severity": "critical",
                    "message": "Critical issue",
                    "suggestion": "Fix this",
                    "line": 5
                },
                {
                    "severity": "high",
                    "message": "High issue",
                    "suggestion": "Consider this",
                    "line": None
                }
            ]
        }
        result = format_review_report(report)
        assert "Critical issue" in result
        assert "High issue" in result
        assert "line 5" in result
    
    def test_format_truncates_many_issues(self):
        """Test formatting truncates many issues."""
        issues = [
            {
                "severity": "info",
                "message": f"Issue {i}",
                "suggestion": "Fix",
                "line": None
            }
            for i in range(10)
        ]
        
        report = {
            "filepath": "test.py",
            "quality_score": 50,
            "total_issues": 10,
            "by_severity": {"info": 10},
            "issues": issues
        }
        result = format_review_report(report)
        assert "... and 5 more issues" in result
