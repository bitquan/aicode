"""
Dependency Resolver — parse pyproject.toml / requirements.txt, detect
version conflicts, duplicate packages, and suggest upgrade paths.
"""

import re
from pathlib import Path
from typing import Any


# ─── Parsing helpers ──────────────────────────────────────────────────────────

_REQ_LINE_RE = re.compile(
    r"""^(?P<name>[A-Za-z0-9_\-\.]+)   # package name
         \s*
         (?P<spec>[><=!~^][^;\s]*)?     # version specifier (optional)
    """,
    re.VERBOSE,
)

_PYPROJECT_DEP_RE = re.compile(
    r'"(?P<name>[A-Za-z0-9_\-\.]+)\s*(?P<spec>[><=!~^][^"]*?)?"',
)

# Loose heuristic: packages known to have had breaking releases recently.
# A real implementation would query PyPI; we keep it offline-safe.
_KNOWN_MAJOR_UPGRADES: dict[str, str] = {
    "django": "5.0",
    "flask": "3.0",
    "fastapi": "0.110",
    "pydantic": "2.0",
    "sqlalchemy": "2.0",
    "celery": "5.0",
    "pytest": "8.0",
    "numpy": "2.0",
    "pandas": "2.0",
    "requests": "2.32",
    "aiohttp": "3.9",
    "httpx": "0.27",
}

_EOL_PACKAGES: set[str] = {"python-dateutil"}  # add more as needed


def _normalise(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


# ─── Resolver ────────────────────────────────────────────────────────────────

class DependencyResolver:
    """Parse project dependencies and surface conflicts / upgrade suggestions."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    # ── Public API ────────────────────────────────────────────────────────────

    def analyse(self) -> dict[str, Any]:
        """Auto-detect dependency file and return analysis report."""
        for candidate in ("pyproject.toml", "requirements.txt", "requirements-dev.txt"):
            p = self.workspace_root / candidate
            if p.exists():
                return self.analyse_file(str(p))
        return {"error": "No dependency file found (pyproject.toml / requirements.txt)."}

    def analyse_file(self, file_path: str) -> dict[str, Any]:
        """Analyse the given requirements/pyproject file."""
        path = Path(file_path) if Path(file_path).is_absolute() else self.workspace_root / file_path
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".toml":
            deps = self._parse_pyproject(text)
        else:
            deps = self._parse_requirements(text)

        conflicts = self._detect_conflicts(deps)
        upgrades = self._suggest_upgrades(deps)
        eol = [d for d in deps if _normalise(d["name"]) in {_normalise(e) for e in _EOL_PACKAGES}]

        return {
            "file": str(path.relative_to(self.workspace_root)),
            "total_packages": len(deps),
            "packages": deps,
            "conflicts": conflicts,
            "upgrade_suggestions": upgrades,
            "eol_packages": eol,
            "health": "GOOD" if not conflicts and not eol else "NEEDS_ATTENTION",
        }

    def suggest_pinned_versions(self, deps: list[dict]) -> list[str]:
        """Return a requirements.txt-style list with suggested pinned versions."""
        lines = []
        for d in deps:
            name = d["name"]
            spec = d.get("spec") or ""
            suggestion = _KNOWN_MAJOR_UPGRADES.get(_normalise(name))
            if suggestion and not spec:
                lines.append(f"{name}>={suggestion}")
            else:
                lines.append(f"{name}{spec}" if spec else name)
        return lines

    # ── Internals ─────────────────────────────────────────────────────────────

    def _parse_requirements(self, text: str) -> list[dict]:
        deps = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            m = _REQ_LINE_RE.match(line)
            if m:
                deps.append({"name": m.group("name"), "spec": m.group("spec") or ""})
        return deps

    def _parse_pyproject(self, text: str) -> list[dict]:
        deps = []
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if "dependencies" in stripped and "[" in stripped:
                in_deps = True
            elif in_deps and stripped.startswith("["):
                in_deps = False
            if in_deps:
                for m in _PYPROJECT_DEP_RE.finditer(line):
                    deps.append({"name": m.group("name"), "spec": m.group("spec") or ""})
        return deps

    def _detect_conflicts(self, deps: list[dict]) -> list[dict]:
        """Flag packages declared more than once with different specifiers."""
        seen: dict[str, list[dict]] = {}
        for d in deps:
            key = _normalise(d["name"])
            seen.setdefault(key, []).append(d)
        conflicts = []
        for key, entries in seen.items():
            if len(entries) > 1:
                specs = {e.get("spec", "") for e in entries}
                if len(specs) > 1:
                    conflicts.append({
                        "package": entries[0]["name"],
                        "specs": list(specs),
                        "message": "Duplicate declarations with conflicting specifiers.",
                    })
        return conflicts

    def _suggest_upgrades(self, deps: list[dict]) -> list[dict]:
        suggestions = []
        for d in deps:
            latest = _KNOWN_MAJOR_UPGRADES.get(_normalise(d["name"]))
            if latest:
                spec = d.get("spec", "")
                # Only recommend if no pinned upper-bound or using an old lower-bound
                if not spec or re.search(r"[<>]=?\s*\d", spec) is None:
                    suggestions.append({
                        "package": d["name"],
                        "current_spec": spec or "(unpinned)",
                        "suggested": f">={latest}",
                        "note": "Major version available — review changelog for breaking changes.",
                    })
        return suggestions
