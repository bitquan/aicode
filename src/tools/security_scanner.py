"""
Security Scanner — identify common security vulnerabilities in Python source code.
Checks for: hardcoded secrets, SQL injection patterns, unsafe deserialization,
shell injection, weak crypto, open redirects, and missing input validation.
"""

import re
import ast
from pathlib import Path
from typing import Any


# ─── Rule Definitions ─────────────────────────────────────────────────────────

RULES = [
    {
        "id": "SEC001",
        "name": "Hardcoded Secret",
        "severity": "CRITICAL",
        "pattern": re.compile(
            r'(password|passwd|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{4,}["\']',
            re.IGNORECASE,
        ),
        "description": "Hardcoded credential found. Use environment variables instead.",
        "fix": "Replace with os.environ.get('SECRET_NAME') or a secrets manager.",
    },
    {
        "id": "SEC002",
        "name": "SQL Injection Risk",
        "severity": "HIGH",
        "pattern": re.compile(
            r'(execute|executemany|cursor\.execute)\s*\(\s*["\'].*%s|'
            r'execute\s*\(.*f["\'].*{',
            re.IGNORECASE,
        ),
        "description": "Possible SQL injection via string interpolation.",
        "fix": "Use parameterised queries: cursor.execute(sql, (value,))",
    },
    {
        "id": "SEC003",
        "name": "Shell Injection Risk",
        "severity": "HIGH",
        "pattern": re.compile(
            r'(os\.system|subprocess\.call|subprocess\.run|popen)\s*\([^)]*f["\']|'
            r'(os\.system|popen)\s*\([^)]*%',
            re.IGNORECASE,
        ),
        "description": "User-controlled data passed to a shell command.",
        "fix": "Use subprocess with a list of args and shell=False.",
    },
    {
        "id": "SEC004",
        "name": "Unsafe Deserialization",
        "severity": "HIGH",
        "pattern": re.compile(r'\bpickle\.loads?\s*\(|\byaml\.load\s*\(', re.IGNORECASE),
        "description": "Deserialising untrusted data can lead to remote code execution.",
        "fix": "Use pickle only with trusted data; prefer json. Use yaml.safe_load().",
    },
    {
        "id": "SEC005",
        "name": "Weak Hash / Crypto",
        "severity": "MEDIUM",
        "pattern": re.compile(r'\b(md5|sha1)\s*\(|hashlib\.(md5|sha1)\s*\(', re.IGNORECASE),
        "description": "MD5/SHA-1 are cryptographically weak.",
        "fix": "Use hashlib.sha256() or better for security-sensitive hashing.",
    },
    {
        "id": "SEC006",
        "name": "Debug / Assert Left In",
        "severity": "LOW",
        "pattern": re.compile(r'^\s*(assert\s+|breakpoint\(\))'),
        "description": "assert statements and breakpoints should not be in production code.",
        "fix": "Remove or guard behind an environment flag.",
    },
    {
        "id": "SEC007",
        "name": "Open Redirect",
        "severity": "MEDIUM",
        "pattern": re.compile(
            r'redirect\s*\(\s*request\.(args|form|data|json|GET|POST)',
            re.IGNORECASE,
        ),
        "description": "Redirecting to a user-supplied URL can enable phishing.",
        "fix": "Validate and whitelist redirect URLs before using them.",
    },
    {
        "id": "SEC008",
        "name": "Eval / Exec Usage",
        "severity": "CRITICAL",
        "pattern": re.compile(r'\b(eval|exec)\s*\('),
        "description": "eval/exec with dynamic input is a code-injection vector.",
        "fix": "Avoid eval/exec; use ast.literal_eval for safe parsing.",
    },
]

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ─── Scanner ──────────────────────────────────────────────────────────────────

class SecurityScanner:
    """Scan Python source files for common security vulnerabilities."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def scan_file(self, file_path: str) -> dict[str, Any]:
        """Scan a single file and return findings."""
        path = self._resolve(file_path)
        if not path.exists():
            return {"file": str(path), "findings": [], "error": "File not found"}

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"file": str(path), "findings": [], "error": str(exc)}

        findings = self._scan_text(source, str(path.relative_to(self.workspace_root)))
        return {
            "file": str(path.relative_to(self.workspace_root)),
            "findings": findings,
            "total": len(findings),
            "critical": sum(1 for f in findings if f["severity"] == "CRITICAL"),
            "high": sum(1 for f in findings if f["severity"] == "HIGH"),
        }

    def scan_directory(self, target: str = "src/", max_files: int = 50) -> dict[str, Any]:
        """Scan all Python files under *target* and aggregate findings."""
        base = self._resolve(target)
        if not base.exists():
            base = self.workspace_root / "src"

        py_files = sorted(base.rglob("*.py"))[:max_files]
        all_findings: list[dict] = []
        scanned = 0

        for py_file in py_files:
            result = self.scan_file(str(py_file))
            all_findings.extend(result.get("findings", []))
            scanned += 1

        all_findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))

        return {
            "scanned_files": scanned,
            "total_findings": len(all_findings),
            "critical": sum(1 for f in all_findings if f["severity"] == "CRITICAL"),
            "high": sum(1 for f in all_findings if f["severity"] == "HIGH"),
            "medium": sum(1 for f in all_findings if f["severity"] == "MEDIUM"),
            "low": sum(1 for f in all_findings if f["severity"] == "LOW"),
            "findings": all_findings[:30],  # cap output length
        }

    def suggest_fixes(self, findings: list[dict]) -> list[str]:
        """Return actionable fix suggestions for a list of findings."""
        suggestions = []
        seen_ids: set[str] = set()
        for f in findings:
            rule_id = f.get("rule_id", "")
            if rule_id not in seen_ids:
                suggestions.append(
                    f"[{rule_id}][{f['severity']}] {f['rule_name']}: {f['fix']}"
                )
                seen_ids.add(rule_id)
        return suggestions

    # ── Internals ─────────────────────────────────────────────────────────────

    def _scan_text(self, source: str, rel_path: str) -> list[dict]:
        findings = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            for rule in RULES:
                if rule["pattern"].search(line):
                    findings.append(
                        {
                            "file": rel_path,
                            "line": lineno,
                            "rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "severity": rule["severity"],
                            "description": rule["description"],
                            "fix": rule["fix"],
                            "snippet": line.strip()[:120],
                        }
                    )
        return findings

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.workspace_root / p).resolve()
