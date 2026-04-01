from pathlib import Path


PLAYBOOK_TEMPLATES = {
    "incident_response.md": "# Incident Response\n\n## Trigger\n\n## Triage\n\n## Mitigation\n\n## Recovery\n\n## Postmortem\n",
    "rollback.md": "# Rollback Playbook\n\n## Preconditions\n\n## Rollback Steps\n\n## Verification\n\n## Communication\n",
    "hotfix.md": "# Hotfix Playbook\n\n## Scope\n\n## Fast Validation\n\n## Release Steps\n\n## Follow-up\n",
}


def scaffold_playbooks(workspace_root: str) -> dict:
    root = Path(workspace_root).resolve()
    playbook_dir = root / "docs" / "playbooks"
    playbook_dir.mkdir(parents=True, exist_ok=True)

    created = []
    existing = []
    for filename, content in PLAYBOOK_TEMPLATES.items():
        path = playbook_dir / filename
        if path.exists():
            existing.append(path.as_posix())
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path.as_posix())

    return {"created": created, "existing": existing}


def get_playbook_status(workspace_root: str) -> dict:
    root = Path(workspace_root).resolve()
    playbook_dir = root / "docs" / "playbooks"
    status = {}
    for filename in PLAYBOOK_TEMPLATES:
        status[filename] = (playbook_dir / filename).exists()
    return status
