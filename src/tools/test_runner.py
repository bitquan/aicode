import shlex
import subprocess

from src.tools.command_guard import validate_command


def run_test_command(command: str, timeout: int = 300):
    guard = validate_command(command)
    if not guard["allowed"]:
        return {
            "command": command,
            "success": False,
            "stdout": "",
            "stderr": f"Blocked command: {guard['reason']}",
            "returncode": None,
            "timed_out": False,
        }

    try:
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "success": False,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nTest command timed out.",
            "returncode": None,
            "timed_out": True,
        }
