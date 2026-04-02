import shlex


ALLOWED_BINARIES = {
    "python",
    "python3",
    "pytest",
    "ruff",
    "mypy",
    "npm",
}

DANGEROUS_TOKENS = {
    "rm",
    "sudo",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    ":(){",
}


def validate_command(command: str) -> dict:
    tokens = shlex.split(command)
    if not tokens:
        return {"allowed": False, "reason": "empty command"}

    binary = tokens[0]
    if binary not in ALLOWED_BINARIES and not (binary == "python" and "-m" in tokens):
        return {"allowed": False, "reason": f"binary not allowed: {binary}"}

    lowered = " ".join(tokens).lower()
    for token in DANGEROUS_TOKENS:
        if token in lowered:
            return {"allowed": False, "reason": f"dangerous token detected: {token}"}

    return {"allowed": True, "reason": "ok"}
