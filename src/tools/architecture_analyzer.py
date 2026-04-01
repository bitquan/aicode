"""Architecture analyzer for high-level codebase structure insights."""

from pathlib import Path
from typing import Dict, List


class ArchitectureAnalyzer:
    """Analyzes module layout and import relationships."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def analyze(self, include: str = "src") -> Dict:
        root = self.workspace_root / include
        if not root.exists():
            return {"error": f"Path not found: {include}"}

        py_files = list(root.glob("**/*.py"))
        modules = [self._module_name(path, root) for path in py_files]

        imports = {}
        for file_path in py_files:
            imports[str(file_path.relative_to(self.workspace_root))] = self._extract_imports(file_path)

        layers = self._detect_layers(root)

        return {
            "path": include,
            "python_files": len(py_files),
            "modules": modules[:50],
            "layers": layers,
            "imports": imports,
            "recommendations": self._recommendations(layers, imports),
        }

    def _module_name(self, path: Path, base: Path) -> str:
        relative = path.relative_to(base)
        return str(relative.with_suffix("")).replace("/", ".")

    def _extract_imports(self, file_path: Path) -> List[str]:
        found = []
        for line in file_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                found.append(stripped.replace("import ", "").split(" as ")[0].strip())
            elif stripped.startswith("from ") and " import " in stripped:
                found.append(stripped.split(" import ")[0].replace("from ", "").strip())
        return found

    def _detect_layers(self, root: Path) -> Dict:
        top_dirs = [p.name for p in root.iterdir() if p.is_dir()]
        guessed = {
            "api": [d for d in top_dirs if "api" in d or "server" in d],
            "domain": [d for d in top_dirs if "model" in d or "agent" in d],
            "infra": [d for d in top_dirs if "tool" in d or "db" in d or "storage" in d],
            "ui": [d for d in top_dirs if "ui" in d or "view" in d],
        }
        return guessed

    def _recommendations(self, layers: Dict, imports: Dict[str, List[str]]) -> List[str]:
        recommendations = []

        if not layers.get("api"):
            recommendations.append("Consider an explicit API/application boundary module.")
        if not layers.get("domain"):
            recommendations.append("Consider grouping core business logic into a dedicated domain package.")
        if len(imports) > 40:
            recommendations.append("Large module surface detected; add architectural ownership docs per package.")

        cross_imports = 0
        for values in imports.values():
            if any("src.tools" in item for item in values) and any("src.agents" in item for item in values):
                cross_imports += 1
        if cross_imports > 8:
            recommendations.append("High tools/agents coupling detected; consider facades or interfaces.")

        if not recommendations:
            recommendations.append("Architecture looks balanced for current size.")

        return recommendations
