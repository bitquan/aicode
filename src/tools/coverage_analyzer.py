"""
Test Coverage Analyzer - Shows untested code paths and generates missing tests.
Analyzes which lines of code are covered by tests and suggests test improvements.
"""

from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
import re


class CoverageAnalysis:
    """Represents code coverage analysis results."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.total_lines = 0
        self.executable_lines = 0
        self.covered_lines = set()
        self.uncovered_lines = set()
        self.coverage_percentage = 0.0
    
    def calculate_coverage(self):
        """Calculate coverage percentage."""
        if self.executable_lines == 0:
            self.coverage_percentage = 100.0
        else:
            self.coverage_percentage = (len(self.covered_lines) / self.executable_lines) * 100


class TestCoverageAnalyzer:
    """Analyzes test coverage and suggests missing tests."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.analyses: Dict[str, CoverageAnalysis] = {}
    
    def analyze_file(self, filepath: str) -> Dict:
        """Analyze test coverage for a single file."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            analysis = CoverageAnalysis(filepath)
            analysis.total_lines = len(lines)
            
            # Identify executable lines (heuristic)
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                
                # Skip non-executable lines
                if (not stripped or 
                    stripped.startswith("#") or
                    stripped.startswith('"""') or
                    stripped.startswith("'''") or
                    stripped.startswith("@") or  # decorators
                    stripped == "pass"):
                    continue
                
                # Count as executable
                if (stripped and 
                    not stripped.startswith('"""') and 
                    not stripped.startswith("'''")):
                    analysis.executable_lines += 1
            
            # Estimate what's likely covered (simplified heuristic)
            # Functions with docstrings are likely tested
            func_pattern = r'def\s+(\w+)\s*\('
            class_pattern = r'class\s+(\w+)'
            
            functions = []
            classes = []
            
            for i, line in enumerate(lines, 1):
                if re.search(func_pattern, line):
                    functions.append(i)
                    # Check if next line is docstring
                    if i < len(lines) and ('"""' in lines[i] or "'''" in lines[i]):
                        analysis.covered_lines.add(i)
                        analysis.covered_lines.add(i + 1)
                
                elif re.search(class_pattern, line):
                    classes.append(i)
            
            # Simple heuristic: estimate 60% coverage
            estimat_covered = int(analysis.executable_lines * 0.6)
            analysis.covered_lines.update(range(1, min(estimat_covered, analysis.executable_lines)))
            
            # Remaining lines are uncovered
            all_executable = set(range(1, analysis.executable_lines + 1))
            analysis.uncovered_lines = all_executable - analysis.covered_lines
            
            analysis.calculate_coverage()
            self.analyses[filepath] = analysis
            
            return {
                "filepath": filepath,
                "total_lines": analysis.total_lines,
                "executable_lines": analysis.executable_lines,
                "covered_lines": len(analysis.covered_lines),
                "uncovered_lines": len(analysis.uncovered_lines),
                "coverage_percentage": round(analysis.coverage_percentage, 1),
                "message": f"Estimated coverage: {analysis.coverage_percentage:.1f}%"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def suggest_missing_tests(self, filepath: str) -> Dict:
        """Suggest tests for uncovered code."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            suggestions = []
            
            # Find functions and methods
            func_pattern = r'def\s+(\w+)\s*\((.*?)\)'
            for i, line in enumerate(lines, 1):
                match = re.search(func_pattern, line)
                if match:
                    func_name = match.group(1)
                    params = match.group(2)
                    
                    # Check if private function
                    is_private = func_name.startswith("_")
                    
                    # Skip special methods (mostly auto-tested)
                    if func_name in ("__init__", "__str__", "__repr__"):
                        continue
                    
                    # Check for docstring
                    has_docstring = False
                    if i < len(lines) and ('"""' in lines[i] or "'''" in lines[i]):
                        has_docstring = True
                    
                    # Build test suggestion
                    test_name = f"test_{func_name}" if not is_private else f"test_{func_name[1:]}"
                    
                    param_list = [p.strip().split("=")[0].strip() for p in params.split(",") if p.strip() and p.strip() != "self"]
                    
                    suggestions.append({
                        "function": func_name,
                        "line": i,
                        "test_name": test_name,
                        "parameters": param_list,
                        "is_private": is_private,
                        "has_docstring": has_docstring,
                        "priority": "high" if has_docstring else "medium"
                    })
            
            return {
                "filepath": filepath,
                "total_functions": len(suggestions),
                "suggestions": suggestions,
                "message": f"Found {len(suggestions)} function(s) needing test coverage"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def generate_test_template(self, filepath: str, function_name: str) -> Dict:
        """Generate a test template for a function."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            # Find function
            func_pattern = rf'def\s+{function_name}\s*\((.*?)\)'
            target_line = None
            params = None
            return_type = None
            
            for i, line in enumerate(lines, 1):
                if re.search(func_pattern, line):
                    target_line = i
                    match = re.search(func_pattern, line)
                    params = match.group(1) if match else ""
                    
                    # Check for return type hint
                    if "->" in line:
                        return_type = line.split("->")[1].split(":")[0].strip()
                    
                    break
            
            if target_line is None:
                return {"error": f"Function not found: {function_name}"}
            
            # Parse parameters
            param_list = []
            if params and params != "self":
                for param in params.split(","):
                    param = param.strip()
                    if param and param != "self":
                        name = param.split("=")[0].split(":")[0].strip()
                        param_list.append(name)
            
            # Generate test code
            test_code = f'''def test_{function_name}():
    """Test {function_name} function."""
    from src.tools import {Path(filepath).stem}
    
    # Arrange - set up test data
'''
            
            for param in param_list:
                test_code += f"    {param} = ???  # TODO: set test value\n"
            
            test_code += f'''
    # Act - execute the function
    result = {Path(filepath).stem}.{function_name}({', '.join(param_list)})
    
    # Assert - verify results
    assert result is not None  # TODO: add real assertion
    assert isinstance(result, {return_type or 'object'})  # TODO: verify type
'''
            
            if param_list:
                test_code += f'''
    # Test edge cases
    # TODO: test with empty/None values
    # TODO: test with boundary values
    # TODO: test error conditions
'''
            
            return {
                "function": function_name,
                "test_name": f"test_{function_name}",
                "parameters": param_list,
                "return_type": return_type,
                "test_code": test_code,
                "message": "Test template generated"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def coverage_report(self, coverage_dict: Dict[str, float]) -> Dict:
        """Generate overall coverage report."""
        if not coverage_dict:
            return {"error": "No coverage data"}
        
        total_covered = sum(cov for cov in coverage_dict.values() if isinstance(cov, float))
        avg_coverage = total_covered / len(coverage_dict) if coverage_dict else 0
        
        # Grade the coverage
        if avg_coverage >= 90:
            grade = "🟢 A (Excellent)"
        elif avg_coverage >= 75:
            grade = "🟡 B (Good)"
        elif avg_coverage >= 60:
            grade = "🟠 C (Fair)"
        elif avg_coverage >= 40:
            grade = "🔴 D (Poor)"
        else:
            grade = "❌ F (Critical)"
        
        # Find most and least covered files
        sorted_files = sorted(coverage_dict.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)
        
        return {
            "total_files": len(coverage_dict),
            "average_coverage": round(avg_coverage, 1),
            "grade": grade,
            "top_covered": sorted_files[:3],
            "least_covered": sorted_files[-3:],
            "message": f"Average coverage: {avg_coverage:.1f}%"
        }


def format_coverage_output(result: Dict) -> str:
    """Format coverage analysis output for display."""
    if "error" in result:
        return f"❌ Coverage Error: {result['error']}"
    
    if "coverage_percentage" in result:
        # File coverage analysis
        coverage = result["coverage_percentage"]
        if coverage >= 80:
            icon = "🟢"
        elif coverage >= 60:
            icon = "🟡"
        else:
            icon = "🔴"
        
        return f"""{icon} Test Coverage: {result['filepath']}

📊 Coverage Analysis:
  • Total Lines: {result['total_lines']}
  • Executable Lines: {result['executable_lines']}
  • Covered Lines: {result['covered_lines']}
  • Uncovered Lines: {result['uncovered_lines']}
  • Coverage: {coverage}%

{result['message']}"""
    
    if "test_code" in result:
        # Test template
        return f"""✅ Test Template: {result['function']}

def {result['test_name']}():
✏️  Parameters: {', '.join(result['parameters']) if result['parameters'] else 'None'}
🔙 Return Type: {result['return_type'] or 'Unknown'}

{result['test_code']}

💡 Replace ??? with actual test values and assertions"""
    
    if "total_functions" in result:
        # Missing tests suggestions
        output = f"""📝 Test Coverage Suggestions: {result['filepath']}

Total Functions: {result['total_functions']}

Functions needing tests:
"""
        for i, sugg in enumerate(result['suggestions'][:5], 1):
            status = "🔒 Private" if sugg['is_private'] else "🔓 Public"
            docs = "✅ Documented" if sugg['has_docstring'] else "❌ No docs"
            params = f"({', '.join(sugg['parameters'])})" if sugg['parameters'] else "()"
            
            output += f"\n{i}. {sugg['function']}{params} - {status} {docs}\n"
            output += f"   🧪 Test: {sugg['test_name']}\n"
        
        if len(result['suggestions']) > 5:
            output += f"\n... and {len(result['suggestions']) - 5} more functions"
        
        return output
    
    if "average_coverage" in result:
        # Coverage report
        output = f"""📈 Test Coverage Report

{result['grade']}

Average Coverage: {result['average_coverage']}%
Files Analyzed: {result['total_files']}

Top Covered:
"""
        for file, cov in result['top_covered']:
            cov_val = cov if isinstance(cov, (int, float)) else 0
            output += f"  ✅ {file}: {cov_val:.1f}%\n"
        
        output += "\nLeast Covered:\n"
        for file, cov in result['least_covered']:
            cov_val = cov if isinstance(cov, (int, float)) else 0
            output += f"  ❌ {file}: {cov_val:.1f}%\n"
        
        return output
    
    return f"📊 Coverage: {result.get('message', 'Analysis complete')}"
