"""Review, debugging, and profiling handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.tools.code_reviewer import format_review_report
from src.tools.coverage_analyzer import format_coverage_output
from src.tools.profiler import format_profile_output

if TYPE_CHECKING:
    from src.tools.chat_engine import ChatEngine


def _handle_debug(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Debug code with execution tracing and breakpoints."""
    target = request.get("target", "src/main.py")

    target_path = engine.workspace_root / target
    if not target_path.exists():
        return f"❌ File not found: {target}"

    if target_path.is_file() and target.endswith(".py"):
        print(f"\n🐛 Analyzing {target} for debugging...\n", flush=True)

        session_result = engine.debugger.start_debug_session(target)
        if "error" in session_result:
            return f"❌ {session_result['error']}"

        trace = engine.debugger.trace_execution(target)
        call_analysis = engine.debugger.analyze_call_patterns(target)

        output = f"""🐛 Debug Session: {target}
    {session_result['message']}

    """

        if "functions" in trace and trace["functions"]:
            output += f"🔵 Functions (Total: {trace['total_functions']}):\n"
            for func_name, line_num in trace["functions"][:10]:
                output += f"  • {func_name} (line {line_num})\n"
            if len(trace["functions"]) > 10:
                output += f"  ... and {len(trace['functions']) - 10} more\n"

        output += f"""
    📊 Call Analysis:
      Internal Calls: {len(call_analysis.get('internal_calls', []))}
      External Calls: {len(call_analysis.get('external_calls', []))}

    💡 Use 'breakpoint <line>' to set breakpoints, 'inspect' to view code, or 'learn' for improvements"""

        engine._log_interaction(f"debug {target}", "debug", True)
        return output

    return f"❌ Target must be a Python file: {target}"


def _handle_profile(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Profile code performance and identify bottlenecks."""
    target = request.get("target", "src/")

    target_path = engine.workspace_root / target

    print(f"\n⚡ Profiling {target}...\n", flush=True)

    if target.endswith("/") or (target_path.exists() and target_path.is_dir()):
        complexity = engine.profiler.analyze_complexity(
            target.rstrip("/") + ".py" if target.endswith("/") else target
        )

        if "error" in complexity:
            optimization = engine.profiler.suggest_optimizations(target_path.parent / "*.py")
            if "error" in optimization:
                return f"❌ Unable to profile: {target}"
            return format_profile_output(optimization)

        suggestions = engine.profiler.suggest_optimizations(
            str(target_path / "*.py") if target.endswith("/") else target
        )

        output = f"""⚡ Performance Profile: {target}

    🎯 Complexity Rating: {complexity.get('complexity_rating', 'Unknown')}

    💡 Optimization Suggestions:
    """

        if "suggestions" in suggestions:
            for i, sugg in enumerate(suggestions["suggestions"][:5], 1):
                output += f"\n{i}. {sugg['category']} ({sugg['priority'].upper()})\n"
                output += f"   Problem: {sugg['issue']}\n"
                output += f"   Solution: {sugg['suggestion']}\n"
                output += f"   Impact: {sugg['potential_speedup']}\n"

        engine._log_interaction(f"profile {target}", "profile", True)
        return output

    if not target_path.exists():
        return f"❌ File not found: {target}"

    if target_path.is_file() and target.endswith(".py"):
        hotspots = engine.profiler.profile_function_calls(target)
        complexity = engine.profiler.analyze_complexity(target)

        if "error" in hotspots:
            return f"❌ {hotspots['error']}"

        formatted = format_profile_output(hotspots)
        complexity_formatted = format_profile_output(complexity)

        engine._log_interaction(f"profile {target}", "profile", True)
        return f"{formatted}\n\n{complexity_formatted}"

    return f"❌ Target must be a Python file or directory: {target}"


def _handle_coverage(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Show test coverage and suggest missing tests."""
    target = request.get("target", "src/")

    target_path = engine.workspace_root / target

    print(f"\n📊 Analyzing test coverage for {target}...\n", flush=True)

    if target.endswith("/") or (target_path.exists() and target_path.is_dir()):
        py_files = list((engine.workspace_root / target).glob("*.py"))
        if not py_files:
            py_files = list((engine.workspace_root / target).glob("**/*.py"))

        coverage_dict: dict[str, Any] = {}

        for py_file in py_files[:5]:
            rel_path = py_file.relative_to(engine.workspace_root)
            analysis = engine.coverage_analyzer.analyze_file(str(rel_path))
            if "coverage_percentage" in analysis:
                coverage_dict[str(rel_path)] = analysis["coverage_percentage"]

        if coverage_dict:
            report = engine.coverage_analyzer.coverage_report(coverage_dict)
            formatted = format_coverage_output(report)

            engine._log_interaction(f"coverage {target}", "coverage", True)
            return formatted

        return f"❌ No Python files found in {target}"

    if not target_path.exists():
        return f"❌ File not found: {target}"

    if target_path.is_file() and target.endswith(".py"):
        analysis = engine.coverage_analyzer.analyze_file(target)
        suggestions = engine.coverage_analyzer.suggest_missing_tests(target)

        if "error" in analysis:
            return f"❌ {analysis['error']}"

        formatted = format_coverage_output(analysis)

        if "suggestions" in suggestions:
            test_suggestions = format_coverage_output(suggestions)
            formatted = f"{formatted}\n\n{test_suggestions}"

        engine._log_interaction(f"coverage {target}", "coverage", True)
        return formatted

    return f"❌ Target must be a Python file or directory: {target}"


def _handle_review(engine: "ChatEngine", request: dict[str, Any]) -> str:
    """Review code quality, security, and best practices."""
    target = request.get("target", "src/")

    target_path = engine.workspace_root / target

    if target.endswith("/") or target_path.is_dir():
        pattern = f"{target}**/*.py" if target.endswith("/") else f"{target}/**/*.py"
        report = engine.code_reviewer.review_codebase(include_patterns=[pattern])

        result = f"""📋 Code Review: {target}
🔍 Analyzed {report['files_reviewed']} files
📊 Average Quality Score: {report['codebase_score']:.1f}/100

Top Issues by File:
"""

        for filepath, file_report in list(report["reviews"].items())[:5]:
            if "error" not in file_report:
                score = file_report.get("quality_score", 0)
                issues = file_report.get("total_issues", 0)
                result += f"  • {filepath}: {score:.0f}/100 ({issues} issues)\n"

        if len(report["reviews"]) > 5:
            result += f"  ... and {len(report['reviews']) - 5} more files\n"

        engine._log_interaction(f"review {target}", "review", True)
        return result

    if not target_path.exists():
        return f"❌ File not found: {target}"

    if target_path.is_file() and target.endswith(".py"):
        print("\n📋 Reviewing code...\n", flush=True)
        report = engine.code_reviewer.review_file(target)

        if "error" in report:
            return f"❌ {report['error']}"

        formatted = format_review_report(report)
        engine._log_interaction(f"review {target}", "review", True)
        return formatted

    return f"❌ Target must be a Python file or directory: {target}"


REVIEW_HANDLERS = {
    "_handle_debug": _handle_debug,
    "_handle_profile": _handle_profile,
    "_handle_coverage": _handle_coverage,
    "_handle_review": _handle_review,
}
