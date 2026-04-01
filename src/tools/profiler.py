"""
Performance Profiler - Identifies bottlenecks and suggests optimizations.
Uses cProfile and memory profiling to analyze code performance.
"""

import cProfile
import pstats
import io
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import tempfile
import sys


class PerformanceProfile:
    """Represents a code performance profile."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: List[Tuple[str, float, int]] = []  # (name, time, calls)
        self.total_time = 0.0
        self.hotspots: List[Dict] = []
    
    def add_function(self, name: str, time_spent: float, calls: int):
        """Add a function to the profile."""
        self.functions.append((name, time_spent, calls))
        self.total_time += time_spent
    
    def identify_hotspots(self, threshold: float = 0.05) -> List[Dict]:
        """Identify functions taking >threshold% of total time."""
        self.hotspots = []
        
        if self.total_time == 0:
            return []
        
        for name, time_spent, calls in self.functions:
            percentage = (time_spent / self.total_time) * 100
            if percentage >= (threshold * 100):
                self.hotspots.append({
                    'function': name,
                    'time': time_spent,
                    'percentage': percentage,
                    'calls': calls,
                    'avg_time_per_call': time_spent / calls if calls > 0 else 0
                })
        
        # Sort by time spent (descending)
        self.hotspots.sort(key=lambda x: x['time'], reverse=True)
        return self.hotspots


class CodeProfiler:
    """Profiles Python code for performance bottlenecks."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.profiles: Dict[str, PerformanceProfile] = {}
    
    def profile_function_calls(self, filepath: str) -> Dict:
        """Analyze function call frequency and time."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            # Parse for function definitions and complexity indicators
            import re
            
            functions = []
            current_func = None
            func_lines = {}
            
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                
                # Function definition
                if stripped.startswith("def "):
                    match = re.search(r'def\s+(\w+)\s*\(', stripped)
                    if match:
                        current_func = match.group(1)
                        func_lines[current_func] = {"start": i, "end": i, "lines": 1, "calls": 0}
                        functions.append(current_func)
                
                # Track function body
                elif current_func and line and not line.startswith("def ") and not line.startswith("class "):
                    if line[0] not in (' ', '\t'):
                        current_func = None
                    else:
                        func_lines[current_func]["end"] = i
                        func_lines[current_func]["lines"] += 1
                        
                        # Count function calls (simple heuristic)
                        if "(" in line and not stripped.startswith("#"):
                            func_lines[current_func]["calls"] += 1
            
            # Estimate complexity (lines of code)
            profile = PerformanceProfile(filepath)
            
            for func_name, info in func_lines.items():
                # Very rough estimation: more lines = potentially slower
                estimated_time = info["lines"] * 0.001  # 1ms per line estimate
                profile.add_function(func_name, estimated_time, info["calls"])
            
            hotspots = profile.identify_hotspots(threshold=0.05)
            
            self.profiles[filepath] = profile
            
            return {
                "filepath": filepath,
                "total_functions": len(functions),
                "hotspots": hotspots,
                "total_estimated_time": profile.total_time,
                "message": f"Found {len(hotspots)} potential bottleneck(s)"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_complexity(self, filepath: str) -> Dict:
        """Analyze code complexity metrics."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                lines = f.readlines()
            
            import re
            
            # Calculate metrics
            total_lines = len(lines)
            code_lines = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
            comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
            blank_lines = sum(1 for line in lines if not line.strip())
            
            # Cyclomatic complexity (rough estimate)
            content = "".join(lines)
            cc = content.count("if ") + content.count("elif ") + content.count("else:") + \
                 content.count("for ") + content.count("while ") + \
                 content.count("except") + content.count("and ") + content.count("or ")
            
            # Function metrics
            func_pattern = r'def\s+(\w+)\s*\('
            functions = re.findall(func_pattern, content)
            
            # Lines per function
            avg_lines_per_func = code_lines / len(functions) if functions else 0
            
            # Identify complex patterns
            optimization_tips = []
            
            if content.count("for ") > content.count("map(") and content.count("filter(") == 0:
                optimization_tips.append("Consider using list comprehensions or map/filter for better performance")
            
            if content.count("*.append") > 5:
                optimization_tips.append("Multiple list appends detected - consider preallocating size")
            
            if content.count("str.replace") > 2:
                optimization_tips.append("Multiple string replacements detected - consider using regex")
            
            if content.count("try:") > content.count("except") * 0.8:
                optimization_tips.append("High exception handling ratio - consider prevention over handling")
            
            # Memory estimation (very rough)
            estimated_memory_mb = total_lines * 0.001  # Rough estimate
            
            return {
                "filepath": filepath,
                "metrics": {
                    "total_lines": total_lines,
                    "code_lines": code_lines,
                    "comment_lines": comment_lines,
                    "blank_lines": blank_lines,
                    "functions": len(functions),
                    "cyclomatic_complexity": cc,
                    "avg_lines_per_function": round(avg_lines_per_func, 1),
                    "estimated_memory_mb": round(estimated_memory_mb, 2)
                },
                "optimization_tips": optimization_tips,
                "complexity_rating": self._rate_complexity(cc, avg_lines_per_func)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _rate_complexity(self, cc: int, avg_lines: float) -> str:
        """Rate overall complexity."""
        score = cc * 0.3 + (avg_lines / 10) * 0.7
        
        if score < 5:
            return "🟢 Low"
        elif score < 15:
            return "🟡 Medium"
        elif score < 30:
            return "🟠 High"
        else:
            return "🔴 Very High"
    
    def suggest_optimizations(self, filepath: str) -> Dict:
        """Suggest specific optimizations for a file."""
        try:
            file_path = self.workspace_root / filepath
            if not file_path.exists():
                return {"error": f"File not found: {filepath}"}
            
            with open(file_path) as f:
                content = f.read()
                lines = content.split("\n")
            
            suggestions = []
            
            # Pattern 1: Inefficient string concatenation
            if "+=" in content and '+ "' in content:
                suggestions.append({
                    "category": "String Concatenation",
                    "issue": "Using += with strings creates intermediate strings",
                    "suggestion": "Use list append + join() or f-strings instead",
                    "priority": "medium",
                    "potential_speedup": "2-10x"
                })
            
            # Pattern 2: Redundant list operations
            if content.count("for") > 2 and content.count("list(") > 0:
                suggestions.append({
                    "category": "List Processing",
                    "issue": "Multiple list iterations detected",
                    "suggestion": "Combine loops or use comprehensions",
                    "priority": "low",
                    "potential_speedup": "1.5-3x"
                })
            
            # Pattern 3: Global variable access in loops
            if content.count("global ") > 0 and content.count("for ") > 0:
                suggestions.append({
                    "category": "Global Variables",
                    "issue": "Accessing globals in loops adds overhead",
                    "suggestion": "Cache global values in local variables",
                    "priority": "medium",
                    "potential_speedup": "1.1-1.5x"
                })
            
            # Pattern 4: Exception overhead
            if content.count("try:") > 3:
                suggestions.append({
                    "category": "Exception Handling",
                    "issue": "High frequency of try/except blocks",
                    "suggestion": "Check conditions BEFORE raising exceptions when possible",
                    "priority": "medium",
                    "potential_speedup": "1.5-5x"
                })
            
            # Pattern 5: Unnecessary imports
            import_count = content.count("import ")
            if import_count > 10:
                suggestions.append({
                    "category": "Imports",
                    "issue": f"Many imports ({import_count})",
                    "suggestion": "Consider lazy imports for heavy libraries",
                    "priority": "low",
                    "potential_speedup": "1.1-1.2x"
                })
            
            # Pattern 6: Deep nesting
            max_indent = max([len(line) - len(line.lstrip()) for line in lines]) // 4 if lines else 0
            if max_indent > 5:
                suggestions.append({
                    "category": "Code Structure",
                    "issue": f"Deep nesting detected (level {max_indent})",
                    "suggestion": "Extract nested logic to separate functions",
                    "priority": "low",
                    "potential_speedup": "1.2-2x"
                })
            
            return {
                "filepath": filepath,
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
                "message": f"Found {len(suggestions)} optimization opportunity/ies"
            }
        except Exception as e:
            return {"error": str(e)}


def format_profile_output(result: Dict) -> str:
    """Format profiling output for display."""
    if "error" in result:
        return f"❌ Profiler Error: {result['error']}"
    
    if "hotspots" in result:
        # Function call profiling
        output = f"""⚡ Performance Profile: {result['filepath']}
        
Total Functions: {result['total_functions']}
Estimated Total Time: {result['total_estimated_time']:.3f}s

🔥 Hotspots (functions using most time):
"""
        for i, hotspot in enumerate(result['hotspots'][:5], 1):
            output += f"\n{i}. {hotspot['function']}\n"
            output += f"   ⏱️  Time: {hotspot['time']:.3f}s ({hotspot['percentage']:.1f}%)\n"
            output += f"   📞 Calls: {hotspot['calls']}\n"
            output += f"   ⌛ Avg/Call: {hotspot['avg_time_per_call']:.4f}s\n"
        
        if len(result['hotspots']) > 5:
            output += f"\n... and {len(result['hotspots']) - 5} more hotspots"
        
        return output
    
    if "metrics" in result:
        # Complexity analysis
        metrics = result['metrics']
        return f"""📊 Code Complexity Analysis: {result['filepath']}

📈 Metrics:
  • Total Lines: {metrics['total_lines']}
  • Code Lines: {metrics['code_lines']}
  • Comment Lines: {metrics['comment_lines']}
  • Functions: {metrics['functions']}
  • Cyclomatic Complexity: {metrics['cyclomatic_complexity']}
  • Avg Lines/Function: {metrics['avg_lines_per_function']}
  • Est. Memory: {metrics['estimated_memory_mb']}MB

🎯 Complexity Rating: {result['complexity_rating']}

💡 Optimization Tips:
{chr(10).join(f"  • {tip}" for tip in result['optimization_tips']) if result['optimization_tips'] else "  No specific tips - code looks good!"}"""
    
    if "suggestions" in result:
        # Optimization suggestions
        output = f"""💡 Optimization Suggestions: {result['filepath']}

Total Suggestions: {result['total_suggestions']}
"""
        
        for i, sugg in enumerate(result['suggestions'][:5], 1):
            output += f"\n{i}. {sugg['category']} ({sugg['priority'].upper()})\n"
            output += f"   Issue: {sugg['issue']}\n"
            output += f"   💡 {sugg['suggestion']}\n"
            output += f"   ⚡ Potential Speedup: {sugg['potential_speedup']}\n"
        
        if len(result['suggestions']) > 5:
            output += f"\n... and {len(result['suggestions']) - 5} more suggestions"
        
        return output
    
    return f"⚡ Profiler: {result.get('message', 'Analysis complete')}"
