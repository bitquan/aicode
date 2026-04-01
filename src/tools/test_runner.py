import shlex
import subprocess


def run_test_command(command: str, timeout: int = 300):
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
