from src.tools.dependency_inventory import read_dependency_inventory


KNOWN_LICENSES = {
    "requests": "Apache-2.0",
    "pytest": "MIT",
}

SPDX_NORMALIZATION = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "bsd-3-clause": "BSD-3-Clause",
}


def _normalize_spdx(value: str) -> str:
    if not value:
        return "UNKNOWN"
    cleaned = value.strip().lower()
    return SPDX_NORMALIZATION.get(cleaned, value.strip())


def scan_dependency_licenses(workspace_root: str) -> dict:
    inv = read_dependency_inventory(workspace_root)
    project_license = _normalize_spdx(inv.get("project_license", "UNKNOWN"))
    items = []

    for name, version in inv.get("dependencies", {}).items():
        license_name = _normalize_spdx(KNOWN_LICENSES.get(name, project_license if project_license != "UNKNOWN" else "UNKNOWN"))
        items.append({"name": name, "version": version, "scope": "runtime", "license": license_name})

    for name, version in inv.get("dev_dependencies", {}).items():
        license_name = _normalize_spdx(KNOWN_LICENSES.get(name, project_license if project_license != "UNKNOWN" else "UNKNOWN"))
        items.append({"name": name, "version": version, "scope": "dev", "license": license_name})

    unknown = [row for row in items if row["license"] == "UNKNOWN"]
    return {
        "project_license": project_license,
        "dependencies": items,
        "unknown_count": len(unknown),
        "unknown": unknown,
        "passed": len(unknown) == 0,
    }
