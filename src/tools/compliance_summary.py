from src.tools.dependency_inventory import read_dependency_inventory
from src.tools.license_scanner import scan_dependency_licenses
from src.tools.playbook_manager import get_playbook_status


def build_compliance_summary(workspace_root: str) -> dict:
    deps = read_dependency_inventory(workspace_root)
    licenses = scan_dependency_licenses(workspace_root)
    playbooks = get_playbook_status(workspace_root)
    return {
        "runtime_dep_count": len(deps.get("dependencies", {})),
        "dev_dep_count": len(deps.get("dev_dependencies", {})),
        "license_scan_passed": licenses["passed"],
        "unknown_license_count": licenses["unknown_count"],
        "playbooks_ready": all(playbooks.values()),
        "playbook_status": playbooks,
    }
