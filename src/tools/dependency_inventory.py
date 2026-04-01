from pathlib import Path
import tomllib


def read_dependency_inventory(workspace_root: str) -> dict:
    root = Path(workspace_root).resolve()
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {"dependencies": {}, "dev_dependencies": {}}

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    poetry = data.get("tool", {}).get("poetry", {})
    project_license = poetry.get("license", "UNKNOWN")
    deps = poetry.get("dependencies", {})
    dev_deps = poetry.get("group", {}).get("dev", {}).get("dependencies", {})

    deps = {k: v for k, v in deps.items() if k != "python"}
    return {
        "project_license": project_license,
        "dependencies": deps,
        "dev_dependencies": dev_deps,
    }
