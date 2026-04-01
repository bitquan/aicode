from pathlib import Path


class ReadFirstPolicy:
    def __init__(self):
        self._read_paths = set()

    def record_read(self, relative_path: str):
        self._read_paths.add(relative_path)

    def can_edit(self, relative_path: str) -> bool:
        return relative_path in self._read_paths


def check_read_first(policy: ReadFirstPolicy, relative_path: str):
    if not policy.can_edit(relative_path):
        raise PermissionError(f"Read-first policy violation for path: {relative_path}")
