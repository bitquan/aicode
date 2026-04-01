import re


def classify_failure(stdout: str, stderr: str, timed_out: bool) -> dict:
    raw_output = f"{stdout}\n{stderr}"
    output = raw_output.lower()
    flaky_signals = detect_flaky_signals(raw_output)

    if timed_out:
        category = "timeout"
        hint = "Optimize runtime or remove blocking/infinite loops."
    elif flaky_signals["suspected"]:
        category = "flaky"
        hint = "Potential flaky test behavior detected; stabilize timing/order/global-state assumptions."
    elif "syntaxerror" in output or "invalid syntax" in output:
        category = "syntax"
        hint = "Fix Python syntax and ensure parsable code."
    elif "modulenotfounderror" in output or "importerror" in output:
        category = "dependency"
        hint = "Fix imports or remove unavailable dependencies."
    elif "assert" in output and "failed" in output:
        category = "assertion"
        hint = "Adjust logic to satisfy test expectations."
    elif "typeerror" in output:
        category = "type"
        hint = "Fix argument types and function signatures."
    elif "nameerror" in output:
        category = "name"
        hint = "Define missing names and correct variable references."
    elif "traceback" in output:
        category = "runtime"
        hint = "Fix runtime exception indicated in traceback."
    else:
        category = "unknown"
        hint = "Use test output clues to produce a minimal safe fix."

    summary = _extract_first_error_line(stdout, stderr)
    return {
        "category": category,
        "hint": hint,
        "summary": summary,
        "flaky": flaky_signals,
        "pytest_nodeids": extract_pytest_nodeids(raw_output),
        "raw": raw_output,
    }


def _extract_first_error_line(stdout: str, stderr: str) -> str:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    error_like = [line for line in lines if re.search(r"error|failed|traceback|exception", line, re.IGNORECASE)]
    if error_like:
        return error_like[0]
    return lines[0] if lines else "No diagnostic output captured."


def detect_flaky_signals(output_text: str) -> dict:
    lowered = output_text.lower()
    patterns = [
        "flaky",
        "rerun",
        "passed on rerun",
        "random",
        "intermittent",
        "race condition",
    ]
    matches = [token for token in patterns if token in lowered]
    return {"suspected": bool(matches), "signals": matches}


def extract_pytest_nodeids(output_text: str) -> list[str]:
    nodeid_regex = r"([\w./-]+\.py::[\w\[\]-]+(?:\[[^\]]+\])?)"
    found = re.findall(nodeid_regex, output_text)
    unique = []
    seen = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
