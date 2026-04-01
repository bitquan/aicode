"""
Tests for Performance Profiler
"""

import pytest
from pathlib import Path
from src.tools.profiler import CodeProfiler, PerformanceProfile, format_profile_output


class TestPerformanceProfile:
    """Test PerformanceProfile functionality."""
    
    def test_initialization(self):
        """Test PerformanceProfile initialization."""
        profile = PerformanceProfile("test.py")
        assert profile.filepath == "test.py"
        assert profile.functions == []
        assert profile.total_time == 0.0
    
    def test_add_function(self):
        """Test adding functions to profile."""
        profile = PerformanceProfile("test.py")
        profile.add_function("func1", 0.5, 10)
        profile.add_function("func2", 0.3, 5)
        
        assert len(profile.functions) == 2
        assert profile.total_time == 0.8
    
    def test_identify_hotspots(self):
        """Test hotspot identification."""
        profile = PerformanceProfile("test.py")
        profile.add_function("slow_func", 0.8, 5)
        profile.add_function("fast_func", 0.2, 100)
        
        hotspots = profile.identify_hotspots(threshold=0.30)
        assert len(hotspots) > 0
        assert hotspots[0]['function'] == "slow_func"
        
    def test_hotspot_calculation(self):
        """Test hotspot percentage calculations."""
        profile = PerformanceProfile("test.py")
        profile.add_function("func", 50, 10)  # 50units of total 100
        profile.add_function("other", 50, 5)  # Other function
        
        hotspots = profile.identify_hotspots(threshold=0.30)
        assert hotspots[0]['percentage'] == 50.0


class TestCodeProfiler:
    """Test CodeProfiler functionality."""
    
    @pytest.fixture
    def profiler(self, tmp_path):
        """Create a profiler with test files."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("""
def slow_function(items):
    result = []
    for item in items:
        result.append(process(item))
    return result

def fast_function(x):
    return x * 2

def process(item):
    total = 0
    for i in range(100):
        total += i
    return total
""")
        return CodeProfiler(str(tmp_path))
    
    def test_profile_function_calls(self, profiler):
        """Test function call profiling."""
        result = profiler.profile_function_calls("sample.py")
        assert "hotspots" in result
        assert result["total_functions"] > 0
    
    def test_analyze_complexity(self, profiler):
        """Test complexity analysis."""
        result = profiler.analyze_complexity("sample.py")
        assert "metrics" in result
        metrics = result["metrics"]
        assert metrics["total_lines"] > 0
        assert metrics["functions"] > 0
        assert metrics["cyclomatic_complexity"] >= 0
    
    def test_complexity_rating(self, profiler):
        """Test complexity rating."""
        result = profiler.analyze_complexity("sample.py")
        assert "complexity_rating" in result
        assert "🟢" in result["complexity_rating"] or "🟡" in result["complexity_rating"] or "🟠" in result["complexity_rating"]
    
    def test_suggest_optimizations(self, profiler):
        """Test optimization suggestions."""
        result = profiler.suggest_optimizations("sample.py")
        assert "suggestions" in result
        # Should have at least some suggestions
    
    def test_file_not_found(self, profiler):
        """Test handling of missing file."""
        result = profiler.profile_function_calls("nonexistent.py")
        assert "error" in result


class TestFormatProfileOutput:
    """Test profile output formatting."""
    
    def test_format_hotspots(self):
        """Test hotspot formatting."""
        result = {
            "filepath": "test.py",
            "total_functions": 3,
            "total_estimated_time": 1.5,
            "hotspots": [
                {
                    "function": "slow_func",
                    "time": 0.9,
                    "percentage": 60.0,
                    "calls": 5,
                    "avg_time_per_call": 0.18
                }
            ]
        }
        output = format_profile_output(result)
        assert "Performance Profile" in output
        assert "slow_func" in output
        assert "60.0" in output
    
    def test_format_complexity(self):
        """Test complexity formatting."""
        result = {
            "filepath": "test.py",
            "metrics": {
                "total_lines": 100,
                "code_lines": 80,
                "comment_lines": 10,
                "blank_lines": 10,
                "functions": 5,
                "cyclomatic_complexity": 8,
                "avg_lines_per_function": 16.0,
                "estimated_memory_mb": 0.1
            },
            "complexity_rating": "🟡 Medium",
            "optimization_tips": ["Tip 1", "Tip 2"]
        }
        output = format_profile_output(result)
        assert "Complexity Analysis" in output
        assert "Medium" in output
        assert "Tip 1" in output
    
    def test_format_suggestions(self):
        """Test suggestion formatting."""
        result = {
            "filepath": "test.py",
            "suggestions": [
                {
                    "category": "String Concatenation",
                    "issue": "Using +=",
                    "suggestion": "Use join()",
                    "priority": "medium",
                    "potential_speedup": "2-10x"
                }
            ],
            "total_suggestions": 1
        }
        output = format_profile_output(result)
        assert "Optimization Suggestions" in output
        assert "String Concatenation" in output
        assert "2-10x" in output
    
    def test_format_error(self):
        """Test error formatting."""
        result = {"error": "File not found"}
        output = format_profile_output(result)
        assert "Error" in output


class TestOptimizationSuggestions:
    """Test optimization suggestion generation."""
    
    def test_string_concatenation_detection(self, tmp_path):
        """Test string concatenation optimization detection."""
        test_file = tmp_path / "strings.py"
        test_file.write_text("""
result = ""
for item in items:
    result += "item"
""")
        profiler = CodeProfiler(str(tmp_path))
        result = profiler.suggest_optimizations("strings.py")
        
        assert "suggestions" in result
        # Should suggest string operations optimization
    
    def test_exception_handling_detection(self, tmp_path):
        """Test exception handling pattern detection."""
        test_file = tmp_path / "errors.py"
        test_file.write_text("""
try:
    func1()
except:
    pass

try:
    func2()
except:
    pass

try:
    func3()
except:
    pass

try:
    func4()
except:
    pass
""")
        profiler = CodeProfiler(str(tmp_path))
        result = profiler.suggest_optimizations("errors.py")
        
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0
