"""
Code Review Assistant - Analyzes code quality, security, complexity, and best practices.
Provides actionable recommendations for improvement.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ReviewIssue:
    """Represents a code review issue."""
    severity: str  # "critical", "high", "medium", "low", "info"
    category: str  # "security", "style", "performance", "complexity", "best_practice"
    line: Optional[int]
    message: str
    suggestion: str


class CodeReviewer:
    """Analyzes code for quality, security, and best practices."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.issues: List[ReviewIssue] = []
    
    def review_file(self, filepath: str) -> Dict:
        """Review a single file and return detailed report."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                content = f.read()
            
            lines = content.split('\n')
            
            self.issues = []
            
            # Run all checks
            self._check_security(lines, filepath)
            self._check_style(lines, filepath)
            self._check_complexity(lines, filepath)
            self._check_best_practices(lines, filepath)
            self._check_documentation(lines, filepath)
            
            return self._generate_report(filepath, lines)
        
        except Exception as e:
            return {"error": str(e)}
    
    def _check_security(self, lines: List[str], filepath: str):
        """Check for security vulnerabilities."""
        content = '\n'.join(lines)
        
        # SQL injection patterns - f-strings with SQL keywords
        if re.search(r'f["\'].*?(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM|JOIN|\{.*?\}).*?["\']', content, re.IGNORECASE | re.DOTALL):
            # Check if it's likely used with database operations
            if re.search(r'(execute|query|cursor|db\.|sql)', content, re.IGNORECASE):
                self.issues.append(ReviewIssue(
                    severity="critical",
                    category="security",
                    line=None,
                    message="Potential SQL injection: Using f-strings in SQL queries",
                    suggestion="Use parameterized queries instead: db.query(sql, params=values)"
                ))
        
        # Hard-coded credentials
        if re.search(r'(password|api_key|secret|token)\s*=\s*["\']([^"\']{5,})["\']', content, re.IGNORECASE):
            self.issues.append(ReviewIssue(
                severity="critical",
                category="security",
                line=None,
                message="Hard-coded credentials detected",
                suggestion="Use environment variables: os.environ.get('API_KEY')"
            ))
        
        # Eval/exec usage
        if re.search(r'\b(eval|exec|compile)\s*\(', content):
            self.issues.append(ReviewIssue(
                severity="critical",
                category="security",
                line=None,
                message="Unsafe eval/exec detected - allows arbitrary code execution",
                suggestion="Use safer alternatives like ast.literal_eval() or json.loads()"
            ))
        
        # Pickle usage (unsafe deserialization)
        if 'pickle.load' in content:
            self.issues.append(ReviewIssue(
                severity="high",
                category="security",
                line=None,
                message="pickle.load() can execute arbitrary code - use with untrusted data",
                suggestion="Use JSON or MessagePack for untrusted data serialization"
            ))
    
    def _check_style(self, lines: List[str], filepath: str):
        """Check code style and readability."""
        for i, line in enumerate(lines, 1):
            # Long lines
            if len(line) > 100:
                self.issues.append(ReviewIssue(
                    severity="low",
                    category="style",
                    line=i,
                    message=f"Line too long ({len(line)} chars > 100)",
                    suggestion="Break into multiple lines for readability"
                ))
            
            # Trailing whitespace
            if line.rstrip() != line:
                self.issues.append(ReviewIssue(
                    severity="info",
                    category="style",
                    line=i,
                    message="Trailing whitespace",
                    suggestion="Remove trailing spaces"
                ))
            
            # Multiple statements on one line
            if re.match(r'^\s*[^#]*;\s*[^#\s]', line):
                self.issues.append(ReviewIssue(
                    severity="low",
                    category="style",
                    line=i,
                    message="Multiple statements on one line",
                    suggestion="Use separate lines for each statement"
                ))
    
    def _check_complexity(self, lines: List[str], filepath: str):
        """Check code complexity."""
        content = '\n'.join(lines)
        
        # Deep nesting detection
        for i, line in enumerate(lines, 1):
            indent = len(line) - len(line.lstrip())
            if indent > 24:  # More than 6 levels of nesting (4 spaces per level)
                self.issues.append(ReviewIssue(
                    severity="medium",
                    category="complexity",
                    line=i,
                    message=f"Deep nesting level ({indent//4} levels)",
                    suggestion="Extract nested logic into separate functions"
                ))
                break  # Report only once
        
        # Long functions (rough estimate)
        function_pattern = r'def\s+\w+\s*\('
        functions = list(re.finditer(function_pattern, content))
        
        if functions:
            for match in functions:
                start = match.start()
                func_name = re.search(r'def\s+(\w+)', content[start:]).group(1)
                
                # Simple line count approximation
                func_lines = content[start:].split('\n')
                indent_level = len(func_lines[0]) - len(func_lines[0].lstrip())
                
                line_count = 0
                for line in func_lines[1:]:
                    if line.strip() and not line.strip().startswith('#'):
                        current_indent = len(line) - len(line.lstrip())
                        if current_indent <= indent_level and line.strip() and current_indent > 0:
                            break
                        line_count += 1
                
                if line_count > 30:
                    self.issues.append(ReviewIssue(
                        severity="medium",
                        category="complexity",
                        line=None,
                        message=f"Function '{func_name}' is too long ({line_count} lines)",
                        suggestion="Break into smaller, focused functions"
                    ))
    
    def _check_best_practices(self, lines: List[str], filepath: str):
        """Check for best practice violations."""
        content = '\n'.join(lines)
        
        # Missing docstrings
        if re.search(r'^def\s+\w+\s*\([^)]*\):\s*\n(?!\s*["\'])', content, re.MULTILINE):
            self.issues.append(ReviewIssue(
                severity="low",
                category="best_practice",
                line=None,
                message="Functions without docstrings",
                suggestion='Add docstrings: def func():\n    """"""'
            ))
        
        # Bare except
        if 'except:' in content:
            self.issues.append(ReviewIssue(
                severity="high",
                category="best_practice",
                line=None,
                message="Bare except clause catches all exceptions",
                suggestion="Catch specific exceptions: except ValueError as e:"
            ))
        
        # Global variable usage
        if re.search(r'global\s+\w+', content):
            self.issues.append(ReviewIssue(
                severity="medium",
                category="best_practice",
                line=None,
                message="Global variables make code harder to test and reason about",
                suggestion="Use function parameters and return values instead"
            ))
        
        # Star imports
        if 'from ' in content and ' import *' in content:
            self.issues.append(ReviewIssue(
                severity="medium",
                category="best_practice",
                line=None,
                message="Star imports make it unclear which names are available",
                suggestion="Import specific names: from module import function1, function2"
            ))
        
        # TODO/FIXME comments
        if re.search(r'#\s*(TODO|FIXME|HACK)', content):
            self.issues.append(ReviewIssue(
                severity="info",
                category="best_practice",
                line=None,
                message="TODO/FIXME comments found - unfinished work",
                suggestion="Create an issue or complete the work"
            ))
    
    def _check_documentation(self, lines: List[str], filepath: str):
        """Check documentation quality."""
        content = '\n'.join(lines)
        
        # File docstring missing
        if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
            self.issues.append(ReviewIssue(
                severity="low",
                category="best_practice",
                line=1,
                message="Module docstring missing",
                suggestion='Add at top: """Module description."""'
            ))
        
        # Class docstring
        class_pattern = r'class\s+\w+.*:\s*\n(?!\s*["\'])'
        if re.search(class_pattern, content, re.MULTILINE):
            self.issues.append(ReviewIssue(
                severity="low",
                category="best_practice",
                line=None,
                message="Classes without docstrings",
                suggestion="Add docstrings to all classes"
            ))
    
    def _generate_report(self, filepath: str, lines: List[str]) -> Dict:
        """Generate a comprehensive review report."""
        # Group by severity
        by_severity = {}
        for issue in self.issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)
        
        # Group by category
        by_category = {}
        for issue in self.issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        
        # Calculate quality score
        severity_weights = {"critical": 10, "high": 5, "medium": 2, "low": 1, "info": 0}
        total_score = 100
        for issue in self.issues:
            total_score -= severity_weights.get(issue.severity, 0)
        quality_score = max(0, total_score)
        
        return {
            "filepath": filepath,
            "quality_score": quality_score,
            "total_issues": len(self.issues),
            "by_severity": {
                sev: len(issues) for sev, issues in by_severity.items()
            },
            "by_category": {
                cat: len(issues) for cat, issues in by_category.items()
            },
            "issues": [
                {
                    "severity": issue.severity,
                    "category": issue.category,
                    "line": issue.line,
                    "message": issue.message,
                    "suggestion": issue.suggestion
                }
                for issue in sorted(self.issues, key=lambda x: (
                    ["critical", "high", "medium", "low", "info"].index(x.severity),
                    x.category
                ))
            ]
        }
    
    def review_codebase(self, include_patterns: Optional[List[str]] = None) -> Dict:
        """Review entire codebase or specified patterns."""
        if include_patterns is None:
            include_patterns = ["src/**/*.py"]
        
        files = []
        for pattern in include_patterns:
            files.extend(self.workspace_root.glob(pattern))
        
        reviews = {}
        total_score = 0
        
        for filepath in files:
            rel_path = str(filepath.relative_to(self.workspace_root))
            report = self.review_file(rel_path)
            reviews[rel_path] = report
            if "quality_score" in report:
                total_score += report["quality_score"]
        
        avg_score = total_score / len(reviews) if reviews else 0
        
        return {
            "codebase_score": avg_score,
            "files_reviewed": len(reviews),
            "reviews": reviews
        }


def format_review_report(report: Dict) -> str:
    """Format review report for display."""
    if "error" in report:
        return f"❌ Error: {report['error']}"
    
    filepath = report.get("filepath", "Unknown")
    score = report.get("quality_score", 0)
    total = report.get("total_issues", 0)
    
    # Color-code score
    if score >= 90:
        score_icon = "🟢"
    elif score >= 75:
        score_icon = "🟡"
    else:
        score_icon = "🔴"
    
    result = f"""📋 Code Review: {filepath}

{score_icon} Quality Score: {score}/100
📊 Total Issues: {total}

"""
    
    # By severity
    severity_map = report.get("by_severity", {})
    if severity_map:
        result += "Issues by Severity:\n"
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = severity_map.get(sev, 0)
            if count > 0:
                emoji = {"critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "ℹ️", "info": "💡"}
                result += f"  {emoji.get(sev, '•')} {sev.title()}: {count}\n"
        result += "\n"
    
    # Top issues
    issues = report.get("issues", [])
    if issues:
        result += "Top Issues:\n"
        for issue in issues[:5]:
            severity = issue.get("severity", "info")
            emoji = {"critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "ℹ️", "info": "💡"}
            line = f" (line {issue['line']})" if issue.get("line") else ""
            result += f"\n{emoji.get(severity, '•')} {issue['message']}{line}\n"
            result += f"   💡 {issue['suggestion']}\n"
        
        if len(issues) > 5:
            result += f"\n... and {len(issues) - 5} more issues\n"
    
    return result
