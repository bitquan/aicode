"""Multi-language support utilities for repository analysis."""

from pathlib import Path
from typing import Any


_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".c": "c",
}

_SNIPPETS: dict[str, str] = {
    "python": "def hello(name: str) -> str:\n    return f'Hello, {name}'",
    "javascript": "function hello(name) {\n  return `Hello, ${name}`;\n}",
    "typescript": "export function hello(name: string): string {\n  return `Hello, ${name}`;\n}",
    "go": "func hello(name string) string {\n    return \"Hello, \" + name\n}",
    "rust": "fn hello(name: &str) -> String {\n    format!(\"Hello, {}\", name)\n}",
}


class MultiLanguageSupport:
    """Analyze language distribution and provide starter snippets."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def detect_language(self, file_path: str) -> dict[str, Any]:
        """Detect language from file extension."""
        path = Path(file_path)
        extension = path.suffix.lower()
        language = _LANGUAGE_MAP.get(extension, "unknown")
        return {
            "file": str(file_path),
            "extension": extension,
            "language": language,
            "supported": language != "unknown",
        }

    def language_summary(self, target: str = "src/") -> dict[str, Any]:
        """Return per-language file counts in target path."""
        target_path = (self.workspace_root / target).resolve() if not Path(target).is_absolute() else Path(target)
        if not target_path.exists():
            return {"error": f"Target not found: {target}"}

        language_counts: dict[str, int] = {}
        scanned_files = 0
        for file_path in target_path.rglob("*"):
            if not file_path.is_file():
                continue
            scanned_files += 1
            detected = self.detect_language(str(file_path))
            language = detected["language"]
            language_counts[language] = language_counts.get(language, 0) + 1

        top = sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)
        return {
            "target": str(target_path),
            "scanned_files": scanned_files,
            "languages": [{"language": name, "files": count} for name, count in top],
            "dominant_language": top[0][0] if top else "unknown",
        }

    def starter_snippet(self, language: str) -> dict[str, Any]:
        """Return quick starter snippet for a language."""
        key = language.strip().lower()
        if key not in _SNIPPETS:
            return {"error": f"No snippet available for: {language}"}
        return {"language": key, "snippet": _SNIPPETS[key]}
