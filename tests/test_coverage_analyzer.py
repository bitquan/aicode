"""
Tests for Test Coverage Analyzer
"""

import pytest
from pathlib import Path
from src.tools.coverage_analyzer import TestCoverageAnalyzer as CoverageAnalyzerTool, CoverageAnalysis, format_coverage_output


class TestCoverageAnalysis:
    """Test CoverageAnalysis functionality."""
    
    def test_initialization(self):
        """Test CoverageAnalysis initialization."""
        analysis = CoverageAnalysis("test.py")
        assert analysis.filepath == "test.py"
        assert analysis.executable_lines == 0
        assert analysis.coverage_percentage == 0.0
    
    def test_coverage_calculation(self):
        """Test coverage percentage calculation."""
        analysis = CoverageAnalysis("test.py")
        analysis.executable_lines = 10
        analysis.covered_lines = {1, 2, 3, 4, 5}
        
        analysis.calculate_coverage()
        assert analysis.coverage_percentage == 50.0
    
    def test_full_coverage(self):
        """Test 100% coverage calculation."""
        analysis = CoverageAnalysis("test.py")
        analysis.executable_lines = 5
        analysis.covered_lines = {1, 2, 3, 4, 5}
        
        analysis.calculate_coverage()
        assert analysis.coverage_percentage == 100.0


class TestCoverageAnalyzer:
    """Test TestCoverageAnalyzer functionality."""
    
    @pytest.fixture
    def analyzer(self, tmp_path):
        """Create analyzer with test files."""
        test_file = tmp_path / "code.py"
        test_file.write_text('''
def add(a, b):
    """Add two numbers."""
    return a + b

def multiply(x, y):
    """Multiply two numbers."""
    return x * y

class Calculator:
    """Simple calculator."""
    
    def __init__(self):
        self.result = 0
    
    def divide(self, a, b):
        if b == 0:
            return None
        return a / b
''')
        return CoverageAnalyzerTool(str(tmp_path))
    
    def test_analyze_file(self, analyzer):
        """Test file coverage analysis."""
        result = analyzer.analyze_file("code.py")
        assert "coverage_percentage" in result
        assert result["total_lines"] > 0
        assert result["executable_lines"] > 0
    
    def test_suggest_missing_tests(self, analyzer):
        """Test missing test suggestions."""
        result = analyzer.suggest_missing_tests("code.py")
        assert "suggestions" in result
        assert result["total_functions"] > 0
        
        # Should suggest tests for add, multiply, divide
        func_names = [s["function"] for s in result["suggestions"]]
        assert "add" in func_names or "multiply" in func_names or "divide" in func_names
    
    def test_generate_test_template(self, analyzer):
        """Test test template generation."""
        result = analyzer.generate_test_template("code.py", "add")
        assert result["function"] == "add"
        assert "test_add" in result["test_name"]
        assert "test_code" in result
    
    def test_test_template_with_parameters(self, analyzer):
        """Test template has parameter placeholders."""
        result = analyzer.generate_test_template("code.py", "multiply")
        assert "test_code" in result
        assert "???" in result["test_code"]  # Placeholder for test values
    
    def test_file_not_found(self, analyzer):
        """Test handling of missing file."""
        result = analyzer.analyze_file("nonexistent.py")
        assert "error" in result
    
    def test_function_not_found(self, analyzer):
        """Test handling of missing function."""
        result = analyzer.generate_test_template("code.py", "nonexistent")
        assert "error" in result
    
    def test_coverage_report(self, analyzer):
        """Test overall coverage report."""
        coverage_dict = {
            "file1.py": 95.0,
            "file2.py": 75.0,
            "file3.py": 50.0
        }
        result = analyzer.coverage_report(coverage_dict)
        
        assert "average_coverage" in result
        assert result["total_files"] == 3
        assert "grade" in result
    
    def test_coverage_grades(self, analyzer):
        """Test coverage grading."""
        # Excellent
        result = analyzer.coverage_report({"f1": 95.0})
        assert "A (" in result["grade"]
        
        # Good
        result = analyzer.coverage_report({"f1": 80.0})
        assert "B (" in result["grade"]
        
        # Fair
        result = analyzer.coverage_report({"f1": 65.0})
        assert "C (" in result["grade"]


class TestFormatCoverageOutput:
    """Test coverage output formatting."""
    
    def test_format_file_coverage(self):
        """Test file coverage formatting."""
        result = {
            "filepath": "test.py",
            "total_lines": 50,
            "executable_lines": 40,
            "covered_lines": 32,
            "uncovered_lines": 8,
            "coverage_percentage": 80.0,
            "message": "Good coverage"
        }
        output = format_coverage_output(result)
        assert "Test Coverage" in output
        assert "test.py" in output
        assert "80.0" in output
    
    def test_format_test_template(self):
        """Test template formatting."""
        result = {
            "function": "add",
            "test_name": "test_add",
            "parameters": ["a", "b"],
            "return_type": "int",
            "test_code": "def test_add():\n    result = add(1, 2)\n    assert result == 3",
            "message": "Template generated"
        }
        output = format_coverage_output(result)
        assert "Test Template" in output
        assert "test_add" in output
        assert "???" in output or "Parameters" in output
    
    def test_format_suggestions(self):
        """Test suggestions formatting."""
        result = {
            "filepath": "test.py",
            "total_functions": 3,
            "suggestions": [
                {
                    "function": "add",
                    "line": 5,
                    "test_name": "test_add",
                    "parameters": ["a", "b"],
                    "is_private": False,
                    "has_docstring": True,
                    "priority": "high"
                }
            ]
        }
        output = format_coverage_output(result)
        assert "Test Coverage Suggestions" in output
        assert "add" in output
        assert "test_add" in output
    
    def test_format_coverage_report(self):
        """Test report formatting."""
        result = {
            "average_coverage": 75.0,
            "grade": "🟡 B (Good)",
            "total_files": 5,
            "top_covered": [("file1.py", 95.0), ("file2.py", 90.0)],
            "least_covered": [("file3.py", 40.0), ("file4.py", 35.0)]
        }
        output = format_coverage_output(result)
        assert "Test Coverage Report" in output
        assert "B (Good)" in output
        assert "75.0" in output
    
    def test_format_error(self):
        """Test error formatting."""
        result = {"error": "File not found"}
        output = format_coverage_output(result)
        assert "Error" in output


class TestMissingTestSuggestions:
    """Test missing test suggestion accuracy."""
    
    def test_private_vs_public_functions(self, tmp_path):
        """Test identification of private vs public functions."""
        test_file = tmp_path / "funcs.py"
        test_file.write_text("""
def public_func():
    pass

def _private_func():
    pass

def __dunder_func():
    pass
""")
        analyzer = CoverageAnalyzerTool(str(tmp_path))
        result = analyzer.suggest_missing_tests("funcs.py")
        
        suggestions = {s["function"]: s["is_private"] for s in result["suggestions"]}
        assert suggestions.get("public_func") == False
        assert suggestions.get("_private_func") == True
    
    def test_docstring_detection(self, tmp_path):
        """Test docstring detection in suggestions."""
        test_file = tmp_path / "docs.py"
        test_file.write_text('''
def with_doc():
    """This is documented."""
    pass

def without_doc():
    pass
''')
        analyzer = CoverageAnalyzerTool(str(tmp_path))
        result = analyzer.suggest_missing_tests("docs.py")
        
        suggestions = {s["function"]: s["has_docstring"] for s in result["suggestions"]}
        assert suggestions.get("with_doc") == True
        assert suggestions.get("without_doc") == False
