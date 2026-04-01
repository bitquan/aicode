from src.tools.dependency_inventory import read_dependency_inventory


KNOWN_LICENSES = {
    "requests": "Apache-2.0",
    "pytest": "MIT",
}


def scan_dependency_licenses(workspace_root: str) -> dict:
    inv = read_dependency_inventory(workspace_root)
    items = []

    for name, version in inv.get("dependencies", {}).items():
        license_name = KNOWN_LICENSES.get(name, "UNKNOWN")
        items.append({"name": name, "version": version, "scope": "runtime", "license": license_name})

    for name, version in inv.get("dev_dependencies", {}).items():
        license_name = KNOWN_LICENSES.get(name, "UNKNOWN")
        items.append({"name": name, "version": version, "scope": "dev", "license": license_name})

    unknown = [row for row in items if row["license"] == "UNKNOWN"]
    return {
        "dependencies": items,
        "unknown_count": len(unknown),
        "unknown": unknown,
        "passed": len(unknown) == 0,
    }
