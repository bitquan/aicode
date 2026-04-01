"""
Documentation Generator — auto-generate docstrings, module headers, and
README sections by inspecting Python source AST and signature metadata.
"""

import ast
import inspect
import textwrap
from pathlib import Path
from typing import Any


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _arg_names(args: ast.arguments) -> list[str]:
    names = [a.arg for a in args.args]
    if args.vararg:
        names.append(f"*{args.vararg.arg}")
    if args.kwarg:
        names.append(f"**{args.kwarg.arg}")
    return names


def _has_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", [])
    return bool(body) and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)


# ─── Doc Generator ────────────────────────────────────────────────────────────

class DocGenerator:
    """Generate docstrings, API docs, and README snippets from Python source."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_module_docs(self, file_path: str) -> dict[str, Any]:
        """Parse *file_path* and return generated docstrings for undocumented items."""
        path = self._resolve(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "docstrings": []}

        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {"error": str(exc), "docstrings": []}

        docstrings: list[dict] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _has_docstring(node):
                    docstrings.append(self._make_function_doc(node))
            elif isinstance(node, ast.ClassDef):
                if not _has_docstring(node):
                    docstrings.append(self._make_class_doc(node))

        return {
            "file": str(path.relative_to(self.workspace_root)),
            "undocumented": len(docstrings),
            "docstrings": docstrings,
        }

    def generate_readme_section(self, file_path: str) -> str:
        """Generate a Markdown API reference section for *file_path*."""
        path = self._resolve(file_path)
        if not path.exists():
            return f"# {file_path}\n\n_File not found._\n"

        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return f"# {file_path}\n\n_Syntax error: {exc}_\n"

        lines = [f"## `{path.name}`\n"]
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                lines.append(f"### class `{node.name}`")
                existing = (
                    ast.get_docstring(node) or "_No description available._"
                )
                lines.append(textwrap.fill(existing, 80))
                lines.append("")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = ", ".join(_arg_names(node.args))
                lines.append(f"#### `{node.name}({args})`")
                doc = ast.get_docstring(node) or "_No description available._"
                lines.append(textwrap.fill(doc, 80))
                lines.append("")

        return "\n".join(lines)

    def list_undocumented(self, target: str = "src/") -> dict[str, Any]:
        """Return all functions/classes across *target* that lack docstrings."""
        base = self._resolve(target)
        results: list[dict] = []
        for py_file in sorted(base.rglob("*.py"))[:40]:
            report = self.generate_module_docs(str(py_file))
            if report.get("undocumented", 0) > 0:
                results.append(report)

        total_missing = sum(r["undocumented"] for r in results)
        return {
            "total_missing_docstrings": total_missing,
            "files_affected": len(results),
            "details": results,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _make_function_doc(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
        args = _arg_names(node.args)
        params_block = "\n".join(f"    Args:\n        {a}: _description_" for a in args if a not in ("self", "cls"))
        return {
            "type": "function",
            "name": node.name,
            "line": node.lineno,
            "suggested_docstring": (
                f'"""{node.name.replace("_", " ").capitalize()}.\n\n'
                f"{params_block}\n"
                '    Returns:\n        _description_\n    """\n'
            ),
        }

    def _make_class_doc(self, node: ast.ClassDef) -> dict:
        return {
            "type": "class",
            "name": node.name,
            "line": node.lineno,
            "suggested_docstring": (
                f'"""{node.name} class.\n\n    _Add a one-line description._\n    """\n'
            ),
        }

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (self.workspace_root / p).resolve()
