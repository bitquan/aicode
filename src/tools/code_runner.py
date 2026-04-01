import subprocess
import sys


def run_code(code, timeout=5):
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nExecution timed out.",
            "returncode": None,
            "timed_out": True,
        }